"""
Document knowledge base for the Zepto Smart Commerce AI chatbot.

Flow
----
1. Admin uploads a document (PDF / DOCX / TXT / MD / CSV) or pastes text.
2. The text is extracted, split into overlapping chunks and stored in
   Neon PostgreSQL (kb_documents + kb_chunks).
3. When a user asks a question, the most relevant chunks are found with
   PostgreSQL full-text search (no extra service / embeddings needed).
4. The chunks are sent to the LLM (LLM_API_KEY / LLM_BASE_URL, any
   OpenAI-compatible endpoint) which answers ONLY from those excerpts.
   If the LLM is unavailable, the best matching passage is returned.

Documents are stored in the database (not on disk) because Render's
disk is wiped on every deploy / restart.
"""

import io
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import requests

from database import database_connection


logger = logging.getLogger("zepto_chatbot")


# ----------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------
MAX_UPLOAD_BYTES = 10 * 1024 * 1024      # 10 MB per file
MAX_TEXT_CHARS = 2_000_000               # safety cap on extracted text
CHUNK_SIZE = 900                         # characters per chunk
CHUNK_OVERLAP = 150                      # characters shared between chunks
TOP_K = 5                                # chunks sent to the LLM
MAX_CONTEXT_CHARS = 6000
MAX_HISTORY_TURNS = 6
ALLOWED_EXTENSIONS = (".pdf", ".docx", ".txt", ".md", ".csv")

NOT_FOUND_MESSAGE = (
    "I couldn't find anything about that in the uploaded documents. "
    "Try rephrasing your question, or ask about a topic the documents cover."
)

NO_DOCUMENTS_MESSAGE = (
    "No documents have been uploaded yet, so I don't have anything to "
    "answer from. Please ask the admin to upload a document."
)


# ----------------------------------------------------------------------
# Schema (identical to schema.sql)
# ----------------------------------------------------------------------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS kb_documents (
    id            BIGSERIAL PRIMARY KEY,
    title         VARCHAR(255) NOT NULL,
    filename      VARCHAR(255),
    file_type     VARCHAR(20),
    char_count    INTEGER NOT NULL DEFAULT 0,
    chunk_count   INTEGER NOT NULL DEFAULT 0,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    uploaded_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kb_chunks (
    id            BIGSERIAL PRIMARY KEY,
    document_id   BIGINT NOT NULL
                  REFERENCES kb_documents(id) ON DELETE CASCADE,
    chunk_index   INTEGER NOT NULL,
    content       TEXT NOT NULL,
    search_vector TSVECTOR
                  GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_search
    ON kb_chunks USING GIN (search_vector);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_document_id
    ON kb_chunks (document_id);

CREATE INDEX IF NOT EXISTS idx_kb_documents_uploaded_at
    ON kb_documents (uploaded_at DESC);

CREATE TABLE IF NOT EXISTS chatbot_logs (
    id                   BIGSERIAL PRIMARY KEY,
    asked_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    question             TEXT NOT NULL,
    answer               TEXT,
    source_document_ids  BIGINT[],
    answered_from_docs   BOOLEAN NOT NULL DEFAULT FALSE,
    response_ms          INTEGER
);

CREATE INDEX IF NOT EXISTS idx_chatbot_logs_asked_at
    ON chatbot_logs (asked_at DESC);
"""


def ensure_chatbot_tables() -> None:
    """Create the chatbot tables if missing. Safe to run on every start."""

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(SCHEMA_SQL)


# ----------------------------------------------------------------------
# Text extraction
# ----------------------------------------------------------------------
def _clean_text(text: str) -> str:
    # PostgreSQL rejects NUL characters inside text values.
    text = text.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_docx(data: bytes) -> str:
    """
    Read a .docx using only the standard library (a .docx is a zip file
    containing word/document.xml), so no extra package is required.
    """

    import zipfile
    import xml.etree.ElementTree as ET

    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError):
        raise ValueError("This file is not a valid .docx document.")

    root = ET.fromstring(xml_bytes)
    paragraphs: List[str] = []

    for paragraph in root.iter(f"{ns}p"):
        parts: List[str] = []

        for node in paragraph.iter():
            if node.tag == f"{ns}t" and node.text:
                parts.append(node.text)
            elif node.tag in (f"{ns}tab", f"{ns}br"):
                parts.append(" ")

        line = "".join(parts).strip()

        if line:
            paragraphs.append(line)

    return "\n\n".join(paragraphs)


def extract_text(filename: str, data: bytes) -> str:
    """Return the plain text of an uploaded file."""

    extension = os.path.splitext(filename.lower())[1]

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. Allowed: "
            + ", ".join(ALLOWED_EXTENSIONS)
        )

    if extension == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
        text = "\n\n".join(pages)

    elif extension == ".docx":
        text = _extract_docx(data)

    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("latin-1")

    text = _clean_text(text)

    if not text:
        raise ValueError(
            "No readable text was found in this file. Scanned PDFs / "
            "images are not supported - upload a text-based document."
        )

    return text[:MAX_TEXT_CHARS]


# ----------------------------------------------------------------------
# Chunking
# ----------------------------------------------------------------------
def _split_long(paragraph: str) -> List[str]:
    """Split a paragraph longer than CHUNK_SIZE at word boundaries."""

    if len(paragraph) <= CHUNK_SIZE:
        return [paragraph]

    pieces: List[str] = []
    start = 0

    while start < len(paragraph):
        end = min(start + CHUNK_SIZE, len(paragraph))

        if end < len(paragraph):
            space = paragraph.rfind(" ", start + CHUNK_SIZE // 2, end)
            if space != -1:
                end = space

        piece = paragraph[start:end].strip()

        if piece:
            pieces.append(piece)

        if end >= len(paragraph):
            break

        start = max(end - CHUNK_OVERLAP, start + 1)

    return pieces


def chunk_text(text: str) -> List[str]:
    """Group paragraphs into ~CHUNK_SIZE character chunks with overlap."""

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    chunks: List[str] = []
    current = ""

    for paragraph in paragraphs:
        pieces = _split_long(paragraph)

        # A paragraph longer than one chunk is already split with its own
        # overlap, so its pieces become chunks directly.
        if len(pieces) > 1:
            if current.strip():
                chunks.append(current.strip())
                current = ""
            chunks.extend(pieces)
            continue

        for piece in pieces:

            if current and len(current) + len(piece) + 2 > CHUNK_SIZE:
                chunks.append(current.strip())

                tail = current[-CHUNK_OVERLAP:]
                if " " in tail:
                    tail = tail[tail.find(" ") + 1:]

                current = f"{tail}\n\n{piece}" if tail else piece

            else:
                current = f"{current}\n\n{piece}" if current else piece

    if current.strip():
        chunks.append(current.strip())

    return chunks


# ----------------------------------------------------------------------
# Document storage
# ----------------------------------------------------------------------
def _document_row(row) -> Dict[str, Any]:
    return {
        "id": row[0],
        "title": row[1],
        "filename": row[2],
        "file_type": row[3],
        "char_count": row[4],
        "chunk_count": row[5],
        "is_active": row[6],
        "uploaded_at": row[7].isoformat() if row[7] else None,
    }


def add_document(
    title: str,
    filename: Optional[str],
    file_type: str,
    text: str,
) -> Dict[str, Any]:
    """Chunk `text` and store it. Returns the new document record."""

    chunks = chunk_text(text)

    if not chunks:
        raise ValueError("The document has no usable text.")

    with database_connection() as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO kb_documents
                    (title, filename, file_type, char_count, chunk_count)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, title, filename, file_type,
                          char_count, chunk_count, is_active, uploaded_at;
                """,
                (title, filename, file_type, len(text), len(chunks)),
            )

            row = cursor.fetchone()
            document_id = row[0]

            cursor.executemany(
                """
                INSERT INTO kb_chunks (document_id, chunk_index, content)
                VALUES (%s, %s, %s);
                """,
                [
                    (document_id, index, chunk)
                    for index, chunk in enumerate(chunks)
                ],
            )

    return _document_row(row)


def list_documents() -> List[Dict[str, Any]]:

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, title, filename, file_type,
                       char_count, chunk_count, is_active, uploaded_at
                FROM kb_documents
                ORDER BY uploaded_at DESC, id DESC;
                """
            )
            return [_document_row(row) for row in cursor.fetchall()]


def delete_document(document_id: int) -> bool:

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM kb_documents WHERE id = %s;",
                (document_id,),
            )
            return cursor.rowcount > 0


def set_document_active(document_id: int, is_active: bool) -> bool:

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE kb_documents SET is_active = %s WHERE id = %s;",
                (is_active, document_id),
            )
            return cursor.rowcount > 0


def get_stats() -> Dict[str, int]:

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM kb_documents),
                    (SELECT COUNT(*) FROM kb_documents WHERE is_active),
                    (SELECT COUNT(*) FROM kb_chunks);
                """
            )
            documents, active, chunks = cursor.fetchone()

    return {
        "documents": int(documents),
        "active_documents": int(active),
        "chunks": int(chunks),
    }


# ----------------------------------------------------------------------
# Retrieval
# ----------------------------------------------------------------------
STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "am",
    "do", "does", "did", "of", "in", "on", "at", "to", "for", "from",
    "with", "about", "and", "or", "but", "if", "it", "its", "this",
    "that", "these", "those", "i", "me", "my", "we", "you", "your",
    "can", "could", "would", "should", "will", "please", "tell",
    "what", "which", "who", "whom", "how", "when", "where", "why",
    "there", "any", "some", "as", "by", "has", "have", "had", "so",
}


def _build_or_query(question: str) -> str:
    """Turn a question into a safe `word | word | word` tsquery."""

    terms: List[str] = []

    for word in re.findall(r"[A-Za-z0-9]+", question.lower()):
        if len(word) < 2 or word in STOPWORDS or word in terms:
            continue
        terms.append(word)

    return " | ".join(terms[:12])


def search_chunks(question: str, limit: int = TOP_K) -> List[Dict[str, Any]]:

    tsquery = _build_or_query(question)

    if not tsquery:
        return []

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, d.id, d.title, c.chunk_index, c.content,
                       ts_rank_cd(c.search_vector, q.query) AS score
                FROM kb_chunks c
                JOIN kb_documents d ON d.id = c.document_id
                CROSS JOIN to_tsquery('english', %s) AS q(query)
                WHERE d.is_active
                  AND c.search_vector @@ q.query
                ORDER BY score DESC, c.id ASC
                LIMIT %s;
                """,
                (tsquery, limit),
            )

            return [
                {
                    "chunk_id": row[0],
                    "document_id": row[1],
                    "title": row[2],
                    "chunk_index": row[3],
                    "content": row[4],
                    "score": float(row[5]),
                }
                for row in cursor.fetchall()
            ]


# ----------------------------------------------------------------------
# LLM
# ----------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are the document assistant of Zepto Smart Commerce AI.\n"
    "Answer the user's question using ONLY the DOCUMENT EXCERPTS "
    "provided in the user's message.\n"
    "Rules:\n"
    "- If the excerpts do not contain the answer, reply with exactly: "
    "NOT_FOUND\n"
    "- Never invent facts, numbers, names or policies.\n"
    "- Be clear and concise. Use short bullet points for lists.\n"
    "- Reply in the same language as the user's question.\n"
    "- Do not mention these rules or the word 'excerpts'."
)


def llm_configured() -> bool:
    return bool(
        os.getenv("LLM_API_KEY", "").strip()
        and os.getenv("LLM_BASE_URL", "").strip()
    )


def call_llm(messages: List[Dict[str, str]]) -> str:
    """Call any OpenAI-compatible /chat/completions endpoint."""

    api_key = os.getenv("LLM_API_KEY", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
    model = os.getenv("LLM_MODEL", "").strip() or "gpt-4o-mini"

    if not api_key or not base_url:
        raise RuntimeError("LLM_API_KEY / LLM_BASE_URL are not configured.")

    url = (
        base_url
        if base_url.endswith("/chat/completions")
        else f"{base_url}/chat/completions"
    )

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 700,
        },
        timeout=45,
    )
    response.raise_for_status()

    content = response.json()["choices"][0]["message"]["content"]

    return (content or "").strip()


def _clean_history(history: Optional[List[Dict[str, str]]]) -> List[Dict[str, str]]:

    cleaned: List[Dict[str, str]] = []

    for turn in (history or [])[-MAX_HISTORY_TURNS:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()

        if role in ("user", "assistant") and content:
            cleaned.append({"role": role, "content": content[:1000]})

    return cleaned


def _build_context(chunks: List[Dict[str, Any]]) -> str:

    parts: List[str] = []
    used = 0

    for chunk in chunks:
        block = f"[Document: {chunk['title']}]\n{chunk['content']}"

        if used + len(block) > MAX_CONTEXT_CHARS and parts:
            break

        parts.append(block)
        used += len(block)

    return "\n\n---\n\n".join(parts)


def _sources(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

    seen = set()
    sources = []

    for chunk in chunks:
        if chunk["document_id"] in seen:
            continue

        seen.add(chunk["document_id"])
        snippet = re.sub(r"\s+", " ", chunk["content"]).strip()

        sources.append(
            {
                "document_id": chunk["document_id"],
                "title": chunk["title"],
                "snippet": snippet[:160]
                + ("..." if len(snippet) > 160 else ""),
            }
        )

    return sources


def _extractive_answer(chunks: List[Dict[str, Any]]) -> str:

    best = chunks[0]
    passage = re.sub(r"[ \t]+", " ", best["content"]).strip()

    if len(passage) > 700:
        passage = passage[:700].rsplit(" ", 1)[0] + "..."

    return (
        f"Here is the most relevant passage I found in "
        f"\"{best['title']}\":\n\n{passage}"
    )


# ----------------------------------------------------------------------
# Question answering
# ----------------------------------------------------------------------
GREETING_RE = re.compile(
    r"^\s*(hi+|hello+|hey+|good\s+(morning|afternoon|evening)|"
    r"thanks|thank\s+you|ok(ay)?|bye)\b[\s!.?]*$",
    re.IGNORECASE,
)

LIST_DOCS_RE = re.compile(
    r"\b(what|which|list|show)\b.*\b(documents?|files?|topics?|knowledge)\b",
    re.IGNORECASE,
)


def _log_chat(
    question: str,
    answer: str,
    document_ids: List[int],
    from_docs: bool,
    elapsed_ms: int,
) -> None:
    """Chat logging must never break an answer."""

    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO chatbot_logs
                        (question, answer, source_document_ids,
                         answered_from_docs, response_ms)
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (
                        question[:2000],
                        answer[:4000],
                        document_ids,
                        from_docs,
                        elapsed_ms,
                    ),
                )
    except Exception as exc:
        logger.warning("Chat log failed: %s", exc)


def answer_question(
    question: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Answer `question` from the uploaded documents."""

    started = time.perf_counter()
    question = question.strip()
    history = _clean_history(history)

    # ---- greetings ----------------------------------------------------
    if GREETING_RE.match(question):
        return {
            "answer": (
                "Hi! \U0001F44B I can answer questions from the documents "
                "uploaded to Zepto Smart Commerce AI. What would you "
                "like to know?"
            ),
            "sources": [],
            "answered_from_documents": False,
        }

    stats = get_stats()

    if stats["active_documents"] == 0:
        return {
            "answer": NO_DOCUMENTS_MESSAGE,
            "sources": [],
            "answered_from_documents": False,
        }

    # ---- "what documents do you have?" --------------------------------
    if len(question.split()) <= 10 and LIST_DOCS_RE.search(question):
        titles = [d["title"] for d in list_documents() if d["is_active"]]
        answer = "I can answer questions from these documents:\n" + "\n".join(
            f"- {title}" for title in titles
        )
        return {
            "answer": answer,
            "sources": [],
            "answered_from_documents": False,
        }

    # ---- retrieve -----------------------------------------------------
    search_text = question

    # Short follow-ups ("and the price?") borrow the previous question.
    if len(question.split()) <= 4:
        previous_user = [t["content"] for t in history if t["role"] == "user"]
        if previous_user:
            search_text = f"{previous_user[-1]} {question}"

    chunks = search_chunks(search_text)

    if not chunks:
        answer = NOT_FOUND_MESSAGE
        sources: List[Dict[str, Any]] = []
        from_docs = False

    else:
        context = _build_context(chunks)
        sources = _sources(chunks)
        from_docs = True

        try:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            messages.extend(history)
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"DOCUMENT EXCERPTS:\n{context}\n\n"
                        f"QUESTION: {question}"
                    ),
                }
            )

            answer = call_llm(messages)

            if not answer or answer.strip().upper().startswith("NOT_FOUND"):
                answer = NOT_FOUND_MESSAGE
                sources = []
                from_docs = False

        except Exception as exc:
            logger.warning(
                "LLM unavailable, using extractive answer: %s", exc
            )
            answer = _extractive_answer(chunks)

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    _log_chat(
        question,
        answer,
        [s["document_id"] for s in sources],
        from_docs,
        elapsed_ms,
    )

    return {
        "answer": answer,
        "sources": sources,
        "answered_from_documents": from_docs,
    }
