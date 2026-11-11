"""
Chatbot + admin endpoints.

Public:
    GET  /chatbot/status            widget health check
    POST /chatbot/ask               ask a question about the documents

Admin (header  X-Admin-Token: <ADMIN_TOKEN>):
    GET    /admin                        the admin.html page
    GET    /admin/documents              list documents + stats
    POST   /admin/documents              upload a file (multipart)
    POST   /admin/documents/text         add pasted text
    PATCH  /admin/documents/{id}/active  enable / disable a document
    DELETE /admin/documents/{id}         delete a document
"""

import hmac
import logging
import os
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Deque, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import knowledge_base as kb


logger = logging.getLogger("zepto_chatbot")

router = APIRouter()

ADMIN_PAGE = Path(__file__).resolve().parent / "admin.html"


# ----------------------------------------------------------------------
# Request models
# ----------------------------------------------------------------------
class ChatTurn(BaseModel):
    role: str
    content: str = Field(max_length=4000)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: List[ChatTurn] = Field(default_factory=list)


class TextDocumentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)


class ActiveRequest(BaseModel):
    is_active: bool


# ----------------------------------------------------------------------
# Admin authentication
# ----------------------------------------------------------------------
def require_admin(x_admin_token: Optional[str] = Header(default=None)):

    expected = os.getenv("ADMIN_TOKEN", "").strip()

    if not expected:
        raise HTTPException(
            status_code=503,
            detail="ADMIN_TOKEN is not configured on the server.",
        )

    if not x_admin_token or not hmac.compare_digest(
        x_admin_token.strip().encode("utf-8"),
        expected.encode("utf-8"),
    ):
        raise HTTPException(status_code=401, detail="Invalid admin token.")


# ----------------------------------------------------------------------
# Very small in-memory rate limit for the public /chatbot/ask endpoint
# (protects the LLM quota). 20 questions per minute per visitor.
# ----------------------------------------------------------------------
RATE_LIMIT = 20
RATE_WINDOW_SECONDS = 60
_hits: Dict[str, Deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")

    if forwarded:
        return forwarded.split(",")[0].strip()

    return request.client.host if request.client else "unknown"


def _check_rate_limit(request: Request) -> None:

    now = time.monotonic()
    hits = _hits[_client_ip(request)]

    while hits and now - hits[0] > RATE_WINDOW_SECONDS:
        hits.popleft()

    if len(hits) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Too many questions. Please wait a moment.",
        )

    hits.append(now)


# ----------------------------------------------------------------------
# Public endpoints
# ----------------------------------------------------------------------
@router.get("/chatbot/status", tags=["chatbot"])
def chatbot_status():

    try:
        stats = kb.get_stats()
    except Exception as exc:
        logger.exception("Chatbot status failed: %s", exc)
        raise HTTPException(status_code=503, detail="Database unavailable.")

    return {
        "status": "ok",
        "documents": stats["active_documents"],
        "llm_configured": kb.llm_configured(),
    }


@router.post("/chatbot/ask", tags=["chatbot"])
def chatbot_ask(payload: AskRequest, request: Request):

    _check_rate_limit(request)

    try:
        result = kb.answer_question(
            payload.question,
            [turn.model_dump() for turn in payload.history],
        )

    except Exception as exc:
        logger.exception("Chatbot answer failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="The assistant is temporarily unavailable.",
        )

    return {"status": "success", **result}


# ----------------------------------------------------------------------
# Admin page
# ----------------------------------------------------------------------
@router.get("/admin", include_in_schema=False)
def admin_page():

    if not ADMIN_PAGE.exists():
        raise HTTPException(status_code=404, detail="admin.html not found.")

    return FileResponse(ADMIN_PAGE, media_type="text/html")


# ----------------------------------------------------------------------
# Admin endpoints
# ----------------------------------------------------------------------
@router.get(
    "/admin/documents",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)
def admin_list_documents():

    try:
        return {
            "status": "success",
            "documents": kb.list_documents(),
            "stats": kb.get_stats(),
            "llm_configured": kb.llm_configured(),
        }

    except Exception as exc:
        logger.exception("Listing documents failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/admin/documents",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)
def admin_upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
):

    filename = (file.filename or "document").strip()
    data = file.file.read(kb.MAX_UPLOAD_BYTES + 1)

    if len(data) > kb.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                "File is too large (limit "
                f"{kb.MAX_UPLOAD_BYTES // (1024 * 1024)} MB)."
            ),
        )

    if not data:
        raise HTTPException(status_code=422, detail="The file is empty.")

    try:
        text = kb.extract_text(filename, data)

        document = kb.add_document(
            title=(title or "").strip() or os.path.splitext(filename)[0],
            filename=filename,
            file_type=os.path.splitext(filename.lower())[1].lstrip("."),
            text=text,
        )

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    except Exception as exc:
        logger.exception("Document upload failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Could not process the document: {exc}",
        )

    return {"status": "success", "document": document}


@router.post(
    "/admin/documents/text",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)
def admin_add_text(payload: TextDocumentRequest):

    text = kb._clean_text(payload.content)

    if not text:
        raise HTTPException(status_code=422, detail="The text is empty.")

    try:
        document = kb.add_document(
            title=payload.title.strip(),
            filename=None,
            file_type="text",
            text=text[: kb.MAX_TEXT_CHARS],
        )

    except Exception as exc:
        logger.exception("Adding text document failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return {"status": "success", "document": document}


@router.patch(
    "/admin/documents/{document_id}/active",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)
def admin_set_active(document_id: int, payload: ActiveRequest):

    if not kb.set_document_active(document_id, payload.is_active):
        raise HTTPException(status_code=404, detail="Document not found.")

    return {"status": "success", "id": document_id, "is_active": payload.is_active}


@router.delete(
    "/admin/documents/{document_id}",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)
def admin_delete_document(document_id: int):

    if not kb.delete_document(document_id):
        raise HTTPException(status_code=404, detail="Document not found.")

    return {"status": "success", "deleted": document_id}
