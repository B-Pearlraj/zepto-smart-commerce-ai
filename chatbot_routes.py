"""Additive FastAPI router: never replaces existing endpoints."""
import os
import secrets
import logging
from fastapi import APIRouter, UploadFile, File, Header, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pathlib import Path
from ingest import ingest, ensure_schema, list_documents, delete_document, MAX_BYTES
from rag import answer

router = APIRouter(prefix='/rag', tags=['Document AI Assistant'])
logger = logging.getLogger(__name__)

class ChatRequest(BaseModel):
    question: str = Field(min_length=1,max_length=2000)
    history: list[dict] = Field(default_factory=list,max_length=12)

def admin_auth(authorization: str = Header(default='')):
    token = os.getenv('ADMIN_TOKEN','')
    candidate = authorization.removeprefix('Bearer ').strip()
    if not token or not secrets.compare_digest(candidate, token):
        raise HTTPException(status_code=401,detail='Invalid admin token')

@router.get('/status')
def status():
    return {'status':'available'}

@router.post('/chat')
def chat(payload: ChatRequest):
    try:
        return answer(payload.question,payload.history)
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    except Exception:
        logger.exception('RAG chat failed')
        raise HTTPException(503,'Document assistant temporarily unavailable')

@router.post('/admin/init',dependencies=[Depends(admin_auth)])
def initialize():
    try:
        ensure_schema()
        return {'status':'ready'}
    except Exception:
        logger.exception('RAG schema initialization failed')
        raise HTTPException(503,'Database initialization failed')

@router.post('/admin/upload',dependencies=[Depends(admin_auth)])
async def upload(file: UploadFile = File(...)):
    raw = await file.read(MAX_BYTES+1)
    try:
        return ingest(file.filename or 'unknown',raw)
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    except Exception:
        logger.exception('Document ingestion failed')
        raise HTTPException(503,'Document ingestion failed; check backend logs')

@router.get('/admin/documents',dependencies=[Depends(admin_auth)])
def documents():
    return {'documents':list_documents()}

@router.delete('/admin/documents/{doc_id}',dependencies=[Depends(admin_auth)])
def remove(doc_id:int):
    if not delete_document(doc_id):
        raise HTTPException(404,'Document not found')
    return {'deleted':True}

@router.get('/admin')
def admin_page():
    return FileResponse(Path(__file__).resolve().parent/'admin.html')
