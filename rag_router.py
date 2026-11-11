"""
HTTP layer for the document chat feature.

main.py only needs:

    from rag_router import setup_rag
    setup_rag(app)

Public endpoints (used by the chat box):
    GET  /api/chat/status
    POST /api/chat

Admin endpoints (header  X-Admin-Token: <ADMIN_TOKEN>):
    GET    /api/admin/ping
    GET    /api/admin/documents
    POST   /api/admin/documents              (multipart: file)
    POST   /api/admin/documents/{id}/reindex
    DELETE /api/admin/documents/{id}

Pages / static files:
    GET /admin                 -> widget/admin.html
    GET /widget/chatbot.js     -> the chat box script
    GET /widget/chatbot.css    -> the chat box styles
"""

import hashlib
import hmac
import logging
import os
import re
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Deque, Dict, List, Literal

import psycopg
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Header,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import rag_repository as repo
import rag_service

logger = logging.getLogger("zepto_fastapi")

APP_DIR = Path(__file__).resolve().parent
WIDGET_DIR = APP_DIR / "widget"

MAX_UPLOAD_MB = 10
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

DEFAULT_CORS_ORIGINS = ",".join([
    "https://zepto-smart-commerce-ui.onrender.com",
    "https://zepto-smart-commerce-ai-chatbot.onrender.com",
    "http://localhost:8501",
    "http://127.0.0.1:8501",
])

router = APIRouter()


# ============================================================
# Small in-memory rate limiter (per client IP)
# ============================================================
_hits: Dict[str, Deque[float]] = defaultdict(deque)
_hits_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _recent_count(key: str, window_seconds: int) -> int:
    now = time.monotonic()

    with _hits_lock:
        bucket = _hits[key]

        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()

        return len(bucket)


def _allow(key: str, limit: int, window_seconds: int) -> bool:
    now = time.monotonic()

    with _hits_lock:
        bucket = _hits[key]

        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()

        if len(bucket) >= limit:
            return False

        bucket.append(now)
        return True


# ============================================================
# Admin authentication  (uses your existing ADMIN_TOKEN)
# ============================================================
def require_admin(
    request: Request,
    x_admin_token: str = Header(default=""),
) -> None:
    expected = os.getenv("ADMIN_TOKEN", "").strip()

    if not expected:
        raise HTTPException(
            status_code=503,
            detail="ADMIN_TOKEN is not configured on the server.",
        )

    ip = _client_ip(request)
    failure_key = f"admin-fail:{ip}"

    if _recent_count(failure_key, 300) >= 8:
        raise HTTPException(
            status_code=429,
            detail="Too many wrong tokens. Try again in a few minutes.",
        )

    if not hmac.compare_digest(
        x_admin_token.strip().encode("utf-8"),
        expected.encode("utf-8"),
    ):
        _allow(failure_key, 1_000_000, 300)      # records one failure (5 min window)
        raise HTTPException(status_code=401, detail="Invalid admin token.")


# ============================================================
# Models
# ============================================================
class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: List[ChatTurn] = Field(default_factory=list, max_length=20)


# ============================================================
# Public: chat
# ============================================================
@router.get("/api/chat/status")
def chat_status():
    """Used by the chat box to show the green 'online' dot."""
    try:
        documents = repo.count_documents()
    except Exception:
        logger.exception("Chat status check failed")
        raise HTTPException(status_code=503, detail="Document store unavailable.")

    return {"status": "online", "documents": documents}


@router.post("/api/chat")
def chat(body: ChatRequest, request: Request):
    if not _allow(f"chat:{_client_ip(request)}", limit=20, window_seconds=60):
        raise HTTPException(
            status_code=429,
            detail="You are sending messages too fast. Please wait a moment.",
        )

    question = body.question.strip()

    if not question:
        raise HTTPException(status_code=422, detail="Please type a question.")

    try:
        result = rag_service.answer_question(
            question,
            [turn.model_dump() for turn in body.history],
        )

    except Exception:
        logger.exception("Chat request failed")
        raise HTTPException(
            status_code=503,
            detail="The assistant is temporarily unavailable. Please try again in a moment.",
        )

    return {"status": "success", **result}


# ============================================================
# Admin: documents
# ============================================================
@router.get("/api/admin/ping", dependencies=[Depends(require_admin)])
def admin_ping():
    return {
        "status": "success",
        "llm_configured": rag_service.llm_configured(),
        "chat_model": rag_service.chat_model(),
        "embed_model": rag_service.embed_model(),
        "max_upload_mb": MAX_UPLOAD_MB,
        "allowed_types": sorted(rag_service.ALLOWED_EXTENSIONS),
    }


@router.get("/api/admin/documents", dependencies=[Depends(require_admin)])
def admin_list_documents():
    try:
        documents = repo.list_documents()
    except Exception as exc:
        logger.exception("Listing documents failed")
        raise HTTPException(status_code=500, detail=str(exc))

    return {"status": "success", "count": len(documents), "documents": documents}


@router.post(
    "/api/admin/documents",
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def admin_upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    filename = os.path.basename(file.filename or "").strip()
    filename = re.sub(r"[\x00-\x1f]", "", filename)[:200]
    extension = os.path.splitext(filename.lower())[1]

    if extension not in rag_service.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a PDF, DOCX, TXT or MD file.",
        )

    data = file.file.read(MAX_UPLOAD_BYTES + 1)

    if not data:
        raise HTTPException(status_code=400, detail="The file is empty.")

    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. The limit is {MAX_UPLOAD_MB} MB.",
        )

    content_hash = hashlib.sha256(data).hexdigest()

    try:
        existing = repo.find_document_by_hash(content_hash)
    except Exception as exc:
        logger.exception("Duplicate check failed")
        raise HTTPException(status_code=500, detail=str(exc))

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"This file was already uploaded as '{existing['filename']}'.",
        )

    try:
        text = rag_service.extract_text(filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        logger.exception("Text extraction failed")
        raise HTTPException(status_code=500, detail=str(exc))

    chunks = rag_service.chunk_text(text)

    if not chunks:
        raise HTTPException(status_code=422, detail="No readable text was found in this file.")

    if len(chunks) > rag_service.MAX_CHUNKS_PER_DOCUMENT:
        raise HTTPException(
            status_code=413,
            detail=(
                f"This document is too long ({len(chunks)} sections, the limit is "
                f"{rag_service.MAX_CHUNKS_PER_DOCUMENT}). Please split it into smaller files."
            ),
        )

    try:
        document_id = repo.create_document_with_chunks(
            filename=filename,
            file_type=extension.lstrip("."),
            file_size_bytes=len(data),
            content_hash=content_hash,
            chunks=chunks,
        )

    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="This file was already uploaded.")

    except Exception as exc:
        logger.exception("Saving document failed")
        raise HTTPException(status_code=500, detail=str(exc))

    # Vectors are created after the response is sent; keyword search works at once.
    background_tasks.add_task(rag_service.embed_document, document_id)

    logger.info(
        "Document uploaded | id=%s | file=%s | chunks=%s",
        document_id,
        filename,
        len(chunks),
    )

    return {"status": "success", "document": repo.get_document(document_id)}


@router.post(
    "/api/admin/documents/{document_id}/reindex",
    dependencies=[Depends(require_admin)],
)
def admin_reindex_document(document_id: int, background_tasks: BackgroundTasks):
    try:
        document = repo.get_document(document_id)

        if document is None:
            raise HTTPException(status_code=404, detail="Document not found.")

        repo.set_document_processing(document_id)

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception("Re-index failed")
        raise HTTPException(status_code=500, detail=str(exc))

    background_tasks.add_task(rag_service.embed_document, document_id)

    return {"status": "success", "document": repo.get_document(document_id)}


@router.delete(
    "/api/admin/documents/{document_id}",
    dependencies=[Depends(require_admin)],
)
def admin_delete_document(document_id: int):
    try:
        deleted = repo.delete_document(document_id)
    except Exception as exc:
        logger.exception("Deleting document failed")
        raise HTTPException(status_code=500, detail=str(exc))

    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")

    return {"status": "success", "deleted": document_id}


# ============================================================
# Admin page
# ============================================================
@router.get("/admin", include_in_schema=False)
def admin_page():
    page = WIDGET_DIR / "admin.html"

    if not page.is_file():
        raise HTTPException(
            status_code=404,
            detail="widget/admin.html is missing. Commit the widget folder to the backend repository.",
        )

    return FileResponse(
        page,
        media_type="text/html",
        headers={
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )


# ============================================================
# One call to wire everything into the existing FastAPI app
# ============================================================
def setup_rag(app) -> None:
    # --- CORS: lets the Streamlit site call the chat API from the browser ---
    configured = os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS).strip()

    origins = ["*"] if configured == "*" else [
        origin.strip().rstrip("/")
        for origin in configured.split(",")
        if origin.strip()
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=False,
        max_age=600,
    )

    # --- routes ---
    app.include_router(router)

    # --- chatbot.js / chatbot.css / admin.html ---
    if WIDGET_DIR.is_dir():
        app.mount("/widget", StaticFiles(directory=str(WIDGET_DIR)), name="widget")
    else:
        logger.warning("widget/ folder not found - chat box files will not be served.")

    # --- database tables ---
    @app.on_event("startup")
    def setup_document_tables():
        try:
            repo.init_rag_schema()
            interrupted = repo.mark_interrupted_documents()

            logger.info(
                "Document chat tables ready | interrupted_documents=%s",
                interrupted,
            )

        except Exception as exc:
            logger.exception("Document chat table setup failed: %s", str(exc))
