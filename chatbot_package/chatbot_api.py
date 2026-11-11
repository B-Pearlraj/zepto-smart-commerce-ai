"""
Document chatbot - FastAPI routes.

Plug-in module: main.py only needs

    from chatbot_api import register_chatbot
    register_chatbot(app)

Public endpoints (used by the chat widget)
    POST /chatbot/chat          ask a question
    GET  /chatbot/status        is the bot ready?
    GET  /chatbot/health        diagnostics (tables, documents, AI status)

Admin endpoints (header  X-Admin-Token: <ADMIN_TOKEN>)
    GET    /chatbot/admin/verify
    GET    /chatbot/admin/documents
    POST   /chatbot/admin/documents          upload a file (multipart)
    POST   /chatbot/admin/documents/text     paste text (JSON)
    PATCH  /chatbot/admin/documents/{id}     switch on / off
    DELETE /chatbot/admin/documents/{id}
    GET    /chatbot/admin/stats
    GET    /chatbot/admin/unanswered

Static files served by the API itself
    GET /admin  (and /admin.html)    admin.html
    GET /chatbot/chatbot.js
    GET /chatbot/chatbot.css

Environment variables
    ADMIN_TOKEN          required for the admin endpoints (long random string)
    CHATBOT_CORS_ORIGINS optional, comma separated. Default "*" (the chat
                         endpoint is public and uses no cookies).
    LLM_API_KEY          optional, enables AI-written answers (Groq key)
    LLM_BASE_URL         optional, default https://api.groq.com/openai/v1
    LLM_MODEL            optional, default llama-3.3-70b-versatile
"""

import logging
import os
import secrets
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import chatbot_repository as repo

logger = logging.getLogger("zepto_fastapi")

APP_DIR = Path(__file__).resolve().parent

router = APIRouter(prefix="/chatbot", tags=["Document chatbot"])


# ======================================================================
# MODELS
# ======================================================================

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(default=None, max_length=64)


class TextDocumentRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)


class DocumentToggleRequest(BaseModel):
    is_active: bool


# ======================================================================
# ADMIN AUTHENTICATION
# ======================================================================

def require_admin(x_admin_token: Optional[str]) -> None:
    expected = os.getenv("ADMIN_TOKEN", "").strip()

    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Admin access is not configured. Set ADMIN_TOKEN on the server.",
        )

    if not x_admin_token or not secrets.compare_digest(
        x_admin_token.strip().encode("utf-8"),
        expected.encode("utf-8"),
    ):
        raise HTTPException(status_code=401, detail="Invalid admin token.")


def _document_http_error(exc: repo.DocumentError) -> HTTPException:
    if isinstance(exc, repo.DuplicateDocumentError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


# ======================================================================
# PUBLIC ENDPOINTS
# ======================================================================

@router.post("/chat")
def chat(request: ChatRequest):
    """
    Answer a visitor's question from the uploaded documents.
    """

    try:
        result = repo.answer_question(request.message, request.session_id)

    except Exception as exc:
        logger.exception("Chatbot answer failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="The assistant is unavailable right now. Please try again.",
        )

    return {"status": "success", **result}


@router.get("/status")
def chatbot_status():
    try:
        ready = repo.has_active_documents()
    except Exception as exc:
        logger.exception("Chatbot status check failed: %s", exc)
        raise HTTPException(status_code=503, detail="Database unavailable.")

    return {"status": "success", "ready": ready}


@router.get("/health")
def chatbot_health():
    """
    Open this URL in a browser to see whether the chatbot is installed
    correctly. It never exposes keys or connection strings.
    """

    info = repo.get_diagnostics()
    ready = info["database"] == "connected" and all(info["tables"].values())

    return {"status": "ok" if ready else "needs_attention", **info}


# ======================================================================
# ADMIN ENDPOINTS
# ======================================================================

@router.get("/admin/verify")
def admin_verify(x_admin_token: Optional[str] = Header(default=None)):
    require_admin(x_admin_token)
    return {"status": "success"}


@router.get("/admin/documents")
def admin_list_documents(x_admin_token: Optional[str] = Header(default=None)):
    require_admin(x_admin_token)

    try:
        return {"status": "success", "documents": repo.list_documents()}
    except Exception as exc:
        logger.exception("Listing documents failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/admin/documents", status_code=201)
async def admin_upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    x_admin_token: Optional[str] = Header(default=None),
):
    require_admin(x_admin_token)

    # Read at most one byte over the limit so huge uploads are rejected
    # without loading them fully into memory.
    data = await file.read(repo.MAX_UPLOAD_BYTES + 1)
    filename = file.filename or "document"

    try:
        text = repo.extract_text(filename, data)

        document = repo.add_document(
            title=(title or "").strip() or Path(filename).stem,
            text=text,
            filename=filename,
            content_type=file.content_type,
            file_size_bytes=len(data),
        )

    except repo.DocumentError as exc:
        raise _document_http_error(exc)

    except Exception as exc:
        logger.exception("Document upload failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    logger.info(
        "Chatbot document added | id=%s | chunks=%s",
        document["id"],
        document["chunk_count"],
    )

    return {"status": "success", "document": document}


@router.post("/admin/documents/text", status_code=201)
def admin_add_text_document(
    request: TextDocumentRequest,
    x_admin_token: Optional[str] = Header(default=None),
):
    require_admin(x_admin_token)

    try:
        text = repo.clean_text(request.content)

        if len(text) > repo.MAX_TEXT_CHARS:
            raise repo.DocumentError(
                f"Text is longer than {repo.MAX_TEXT_CHARS:,} characters."
            )

        document = repo.add_document(
            title=request.title,
            text=text,
            filename=None,
            content_type="text/plain",
            file_size_bytes=len(text.encode("utf-8")),
        )

    except repo.DocumentError as exc:
        raise _document_http_error(exc)

    except Exception as exc:
        logger.exception("Text document add failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return {"status": "success", "document": document}


@router.patch("/admin/documents/{document_id}")
def admin_toggle_document(
    document_id: int,
    request: DocumentToggleRequest,
    x_admin_token: Optional[str] = Header(default=None),
):
    require_admin(x_admin_token)

    document = repo.set_document_active(document_id, request.is_active)

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    return {"status": "success", "document": document}


@router.delete("/admin/documents/{document_id}")
def admin_delete_document(
    document_id: int,
    x_admin_token: Optional[str] = Header(default=None),
):
    require_admin(x_admin_token)

    if not repo.delete_document(document_id):
        raise HTTPException(status_code=404, detail="Document not found.")

    return {"status": "success", "deleted_id": document_id}


@router.get("/admin/stats")
def admin_stats(x_admin_token: Optional[str] = Header(default=None)):
    require_admin(x_admin_token)

    try:
        return {"status": "success", "stats": repo.get_stats()}
    except Exception as exc:
        logger.exception("Chatbot stats failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/admin/unanswered")
def admin_unanswered(
    limit: int = 50,
    x_admin_token: Optional[str] = Header(default=None),
):
    require_admin(x_admin_token)

    try:
        return {
            "status": "success",
            "questions": repo.get_unanswered_questions(limit),
        }
    except Exception as exc:
        logger.exception("Unanswered questions failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ======================================================================
# STATIC FILES (admin page + widget assets)
# ======================================================================

def _static_file(filename: str, media_type: str) -> FileResponse:
    path = APP_DIR / filename

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{filename} not found.")

    return FileResponse(path, media_type=media_type)


@router.get("/chatbot.js", include_in_schema=False)
def serve_chatbot_js():
    return _static_file("chatbot.js", "application/javascript")


@router.get("/chatbot.css", include_in_schema=False)
def serve_chatbot_css():
    return _static_file("chatbot.css", "text/css")


# ======================================================================
# REGISTRATION (the only thing main.py needs to call)
# ======================================================================

def register_chatbot(app: FastAPI) -> None:
    """
    Attach the chatbot to an existing FastAPI app:
      - CORS (so the widget can call the API from the Streamlit page
        or any website)
      - the /chatbot routes
      - GET /admin (the admin page)
      - table creation on startup (idempotent; failures are logged and
        never stop the app from starting)
    """

    origins = [
        origin.strip()
        for origin in os.getenv("CHATBOT_CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ] or ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Admin-Token"],
    )

    app.include_router(router)

    @app.get("/admin", include_in_schema=False)
    @app.get("/admin.html", include_in_schema=False)
    def serve_admin_page():
        return _static_file("admin.html", "text/html")

    @app.on_event("startup")
    def setup_chatbot_tables():
        try:
            repo.ensure_chatbot_tables()
            logger.info("Chatbot tables ready")
        except Exception as exc:
            logger.exception("Chatbot table setup failed: %s", exc)

    if not os.getenv("ADMIN_TOKEN", "").strip():
        logger.warning(
            "ADMIN_TOKEN is not set: the chatbot admin page is disabled."
        )
