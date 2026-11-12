"""Safe extraction, chunking and transactional indexing."""
import io
import os
import re
import hashlib
from pathlib import Path
from psycopg.rows import dict_row
from database import database_connection
from rag import embed, vector_literal, EMBED_DIM

MAX_BYTES = int(os.getenv('MAX_DOCUMENT_BYTES', str(8*1024*1024)))
ALLOWED = {'.pdf','.docx','.txt','.md'}


def extract(filename, raw):
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED:
        raise ValueError('Only PDF, DOCX, TXT and MD files are supported')
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError('Document is empty or exceeds upload size limit')
    if suffix == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        if len(reader.pages) > 200:
            raise ValueError('PDF exceeds 200-page limit')
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    elif suffix == '.docx':
        from docx import Document
        doc = Document(io.BytesIO(raw))
        text = '\n'.join([p.text for p in doc.paragraphs] + [cell.text for t in doc.tables for row in t.rows for cell in row.cells])
    else:
        text = raw.decode('utf-8-sig')
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) < 30:
        raise ValueError('No usable text found (scanned PDFs require OCR)')
    return text[:1000000]


def chunks(text, size=1200, overlap=180):
    return [text[i:i+size] for i in range(0,len(text),size-overlap) if text[i:i+size].strip()]


def ensure_schema():
    if EMBED_DIM < 1 or EMBED_DIM > 2000:
        raise RuntimeError('EMBEDDING_DIM must be 1..2000 for this schema')
    with database_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('CREATE EXTENSION IF NOT EXISTS vector')
            cur.execute('''CREATE TABLE IF NOT EXISTS rag_documents (
                id BIGSERIAL PRIMARY KEY, filename TEXT NOT NULL, sha256 TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'ready', created_at TIMESTAMPTZ DEFAULT now())''')
            cur.execute(f'''CREATE TABLE IF NOT EXISTS rag_chunks (
                id BIGSERIAL PRIMARY KEY, document_id BIGINT NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL, content TEXT NOT NULL, embedding vector({EMBED_DIM}) NOT NULL,
                UNIQUE(document_id, chunk_index))''')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_rag_chunks_document ON rag_chunks(document_id)')


def ingest(filename, raw):
    text = extract(filename, raw)
    pieces = chunks(text)
    if len(pieces) > 1000:
        raise ValueError('Document contains too many chunks')
    vectors = []
    for start in range(0,len(pieces),32):
        vectors.extend(embed(pieces[start:start+32]))
    sha = hashlib.sha256(raw).hexdigest()
    clean_name = Path(filename.replace('\\','/')).name[:180]
    with database_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute('INSERT INTO rag_documents(filename,sha256) VALUES(%s,%s) ON CONFLICT(sha256) DO NOTHING RETURNING id', (clean_name,sha))
            result = cur.fetchone()
            if not result:
                raise ValueError('This document has already been uploaded')
            doc_id = result['id']
            for i,(part,vector) in enumerate(zip(pieces,vectors)):
                cur.execute('INSERT INTO rag_chunks(document_id,chunk_index,content,embedding) VALUES(%s,%s,%s,%s::vector)',(doc_id,i,part,vector_literal(vector)))
    return {'document_id':doc_id,'filename':clean_name,'chunks':len(pieces)}


def list_documents():
    with database_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute('''SELECT d.id,d.filename,d.created_at, count(c.id) AS chunks FROM rag_documents d LEFT JOIN rag_chunks c ON c.document_id=d.id GROUP BY d.id ORDER BY d.created_at DESC''')
            return [{**dict(r),'created_at':r['created_at'].isoformat()} for r in cur.fetchall()]


def delete_document(doc_id):
    with database_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM rag_documents WHERE id=%s',(doc_id,))
            return cur.rowcount > 0
