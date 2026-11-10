"""
Portfolio AI Assistant: FastAPI backend.

Public endpoints
    GET  /health                       liveness (and ?deep=1 for DB/key checks)
    POST /api/chat                     answer a visitor question from the knowledge base

Admin endpoints (signed HttpOnly session cookie required)
    POST   /api/admin/login | /logout
    GET    /api/admin/session
    GET    /api/admin/documents
    POST   /api/admin/documents        upload PDF / DOCX / TXT / MD
    GET    /api/admin/documents/{id}/chunks
    DELETE /api/admin/documents/{id}
    GET    /api/admin/search?q=...     retrieval test with similarity scores

Pages
    GET /admin                         the admin dashboard (static/admin.html)
    /static/chatbot.js, /static/chatbot.css
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Literal

import psycopg
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import ingest
import rag
from config import (
    ALLOWED_ORIGINS,
    CHAT_GLOBAL_PER_DAY,
    CHAT_RATE_PER_DAY,
    CHAT_RATE_PER_MIN,
    COOKIE_SECURE,
    DATABASE_URL,
    GEMINI_API_KEY,
    LOGIN_MAX_FAILURES,
    MAX_QUESTION_CHARS,
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_MB,
    SESSION_HOURS,
    STATIC_DIR,
)
from db import DatabaseNotConfigured, connection, init_schema
from llm import LLMError
from security import (
    COOKIE_NAME,
    COOKIE_PATH,
    check_password,
    client_ip,
    limiter,
    make_token,
    require_admin,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("assistant.api")


# ----------------------------------------------------------------------------
# Startup
# ----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_schema()
    except Exception:
        # Do not crash: /health must still answer so Render keeps the service up
        # and the problem is visible in /health?deep=1 and the logs.
        logger.exception("Database schema setup failed")
    yield


app = FastAPI(
    title="Portfolio AI Assistant",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,       # no public Swagger UI / OpenAPI
    redoc_url=None,
    openapi_url=None,
)

# Only the visitor-facing endpoints are called cross-origin (the portfolio
# site). The admin page is served by this same app, so it needs no CORS.
if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
        max_age=600,
    )


@app.middleware("http")
async def request_logging_and_headers(request: Request, call_next):
    started = time.time()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        response = JSONResponse({"detail": "Internal server error."}, status_code=500)

    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")

    if request.url.path.startswith(("/api/admin", "/admin")):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"

    logger.info(
        "%s %s -> %s (%.0f ms)",
        request.method,
        request.url.path,
        response.status_code,
        (time.time() - started) * 1000,
    )
    return response


# ----------------------------------------------------------------------------
# Error helper
# ----------------------------------------------------------------------------
def _service_error(exc: Exception) -> HTTPException:
    """Translate backend failures into short messages that are safe to show."""
    if isinstance(exc, DatabaseNotConfigured):
        return HTTPException(503, "The knowledge base is not configured yet.")
    if isinstance(exc, LLMError):
        logger.error("LLM error: %s", exc)
        return HTTPException(503, "The AI service is temporarily unavailable. Please try again shortly.")
    if isinstance(exc, psycopg.OperationalError):
        logger.error("Database error: %s", exc)
        return HTTPException(503, "The database is waking up. Please try again in a few seconds.")
    logger.exception("Unexpected error")
    return HTTPException(500, "Something went wrong. Please try again.")


# ----------------------------------------------------------------------------
# Health
# ----------------------------------------------------------------------------
@app.get("/health")
def health(deep: int = 0):
    result = {"status": "ok"}

    if deep:
        checks = {
            "database_url_set": bool(DATABASE_URL),
            "gemini_key_set": bool(GEMINI_API_KEY),
        }
        try:
            with connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
                    checks["pgvector_enabled"] = cur.fetchone() is not None
                    cur.execute("SELECT count(*) FROM kb_chunks")
                    checks["chunks_stored"] = cur.fetchone()[0]
            checks["database_connected"] = True
        except Exception as exc:
            checks["database_connected"] = False
            checks["database_error"] = type(exc).__name__
            result["status"] = "degraded"
        result["checks"] = checks

    return result


# ----------------------------------------------------------------------------
# Public chat endpoint
# ----------------------------------------------------------------------------
class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=1200)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    history: list[HistoryItem] = Field(default_factory=list, max_length=10)


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request):
    ip = client_ip(request)

    if not limiter.allow(f"chat-min:{ip}", CHAT_RATE_PER_MIN, 60) or not limiter.allow(
        f"chat-day:{ip}", CHAT_RATE_PER_DAY, 86400
    ):
        raise HTTPException(429, "You're sending messages too quickly. Please wait a moment.")

    if not limiter.allow("chat-global", CHAT_GLOBAL_PER_DAY, 86400):
        raise HTTPException(429, "The assistant has reached its daily limit. Please try again tomorrow.")

    if not payload.message.strip():
        raise HTTPException(422, "Please type a question.")

    history = [{"role": item.role, "content": item.content} for item in payload.history]

    try:
        result = rag.answer_question(payload.message, history)
    except Exception as exc:
        raise _service_error(exc)

    return ChatResponse(answer=result["answer"], sources=result["sources"])


# ----------------------------------------------------------------------------
# Admin: authentication
# ----------------------------------------------------------------------------
class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=200)


@app.post("/api/admin/login")
def admin_login(payload: LoginRequest, request: Request, response: Response):
    ip = client_ip(request)

    if limiter.count(f"login-fail:{ip}", 900) >= LOGIN_MAX_FAILURES:
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")

    if not check_password(payload.password):
        limiter.allow(f"login-fail:{ip}", 10_000, 900)  # records one failure
        logger.warning("Failed admin login from %s", ip)
        raise HTTPException(401, "Incorrect password.")

    response.set_cookie(
        COOKIE_NAME,
        make_token(),
        max_age=SESSION_HOURS * 3600,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        path=COOKIE_PATH,
    )
    return {"ok": True}


@app.post("/api/admin/logout")
def admin_logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH)
    return {"ok": True}


@app.get("/api/admin/session", dependencies=[Depends(require_admin)])
def admin_session():
    return {"authenticated": True, "max_upload_mb": MAX_UPLOAD_MB}


# ----------------------------------------------------------------------------
# Admin: documents
# ----------------------------------------------------------------------------
def _fail_stale_documents() -> None:
    """A deploy/restart can kill a background job; stop showing 'processing' forever."""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE kb_documents
                   SET status = 'failed',
                       error_message = 'Processing was interrupted. Delete this document and upload it again.',
                       updated_at = CURRENT_TIMESTAMP
                 WHERE status = 'processing'
                   AND created_at < CURRENT_TIMESTAMP - INTERVAL '10 minutes'
                """
            )


@app.get("/api/admin/documents", dependencies=[Depends(require_admin)])
def list_documents():
    try:
        _fail_stale_documents()
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, title, filename, file_type, file_size_bytes, status,
                           error_message, char_count, chunk_count, created_at
                      FROM kb_documents
                     ORDER BY created_at DESC
                    """
                )
                rows = cur.fetchall()
    except Exception as exc:
        raise _service_error(exc)

    return {
        "documents": [
            {
                "id": r[0],
                "title": r[1],
                "filename": r[2],
                "file_type": r[3],
                "size_bytes": r[4],
                "status": r[5],
                "error": r[6],
                "char_count": r[7],
                "chunk_count": r[8],
                "created_at": r[9].isoformat(),
            }
            for r in rows
        ]
    }


@app.post("/api/admin/documents", status_code=202, dependencies=[Depends(require_admin)])
def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(""),
):
    filename = os.path.basename(file.filename or "").strip()[:200]
    if not filename:
        raise HTTPException(400, "No file was uploaded.")

    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"The file is larger than the {MAX_UPLOAD_MB} MB limit.")

    try:
        file_type = ingest.validate_file(filename, data)
    except ingest.IngestError as exc:
        raise HTTPException(400, str(exc))

    clean_title = " ".join(title.split())[:150] or os.path.splitext(filename)[0]

    try:
        document_id = ingest.create_document_record(
            clean_title, filename, file_type, len(data), ingest.sha256_hex(data)
        )
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "This exact file has already been uploaded.")
    except Exception as exc:
        raise _service_error(exc)

    # Extraction + embedding can take a while: run it after the response is sent.
    background.add_task(ingest.process_document, document_id, clean_title, filename, data)

    return {"id": document_id, "status": "processing"}


@app.get("/api/admin/documents/{document_id}/chunks", dependencies=[Depends(require_admin)])
def document_chunks(document_id: int):
    try:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT title FROM kb_documents WHERE id = %s", (document_id,))
                doc = cur.fetchone()
                if not doc:
                    raise HTTPException(404, "Document not found.")

                cur.execute(
                    "SELECT chunk_index, content FROM kb_chunks WHERE document_id = %s ORDER BY chunk_index",
                    (document_id,),
                )
                chunks = [{"index": r[0], "content": r[1]} for r in cur.fetchall()]
    except HTTPException:
        raise
    except Exception as exc:
        raise _service_error(exc)

    return {"title": doc[0], "chunks": chunks}


@app.delete("/api/admin/documents/{document_id}", dependencies=[Depends(require_admin)])
def delete_document(document_id: int):
    try:
        with connection() as conn:
            with conn.cursor() as cur:
                # kb_chunks rows are removed automatically (ON DELETE CASCADE)
                cur.execute("DELETE FROM kb_documents WHERE id = %s", (document_id,))
                if cur.rowcount == 0:
                    raise HTTPException(404, "Document not found.")
    except HTTPException:
        raise
    except Exception as exc:
        raise _service_error(exc)

    return {"deleted": document_id}


@app.get("/api/admin/search", dependencies=[Depends(require_admin)])
def search_debug(q: str = "", k: int = 5):
    """Show which chunks a question retrieves and how similar they are."""
    q = " ".join(q.split())[:MAX_QUESTION_CHARS]
    if not q:
        raise HTTPException(400, "Enter a question to test.")

    try:
        results = rag.retrieve(q, top_k=max(1, min(k, 10)))
    except Exception as exc:
        raise _service_error(exc)

    return {
        "min_score": rag.MIN_SCORE,
        "results": [
            {
                "title": r["title"],
                "chunk_index": r["chunk_index"],
                "score": round(r["score"], 4),
                "passes_threshold": r["score"] >= rag.MIN_SCORE,
                "content": r["content"],
            }
            for r in results
        ],
    }


# ----------------------------------------------------------------------------
# Pages and static files
# ----------------------------------------------------------------------------
@app.get("/admin", include_in_schema=False)
def admin_page():
    return FileResponse(STATIC_DIR / "admin.html", media_type="text/html")


@app.get("/", include_in_schema=False)
def root():
    return {"service": "Portfolio AI Assistant", "status": "ok"}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
