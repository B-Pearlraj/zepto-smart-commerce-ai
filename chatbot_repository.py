"""
Document chatbot - storage, text extraction, retrieval and answering.

Used by chatbot_api.py. Reuses the existing `database_connection()`
from database.py, so it talks to the same Neon PostgreSQL database as
the rest of the application. Existing tables are never modified.

How a question is answered
--------------------------
1. The question is turned into search terms (stop-words removed).
2. PostgreSQL full-text search (GIN index on chatbot_chunks) returns the
   best-matching chunks of the ACTIVE documents.
3. Chunks that match too few of the question's terms are discarded.
4. The reply is built only from what is left:
     - default:  the most relevant sentences, quoted from the documents
     - optional: if ANTHROPIC_API_KEY is set, Claude writes a short
                 answer grounded ONLY in those chunks. If anything goes
                 wrong it silently falls back to the default.
5. If nothing relevant is found, the bot says so instead of guessing.
"""

import hashlib
import io
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from database import database_connection

logger = logging.getLogger("zepto_fastapi")


# ======================================================================
# SETTINGS
# ======================================================================

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

MAX_UPLOAD_BYTES = 10 * 1024 * 1024        # 10 MB per file
MAX_TEXT_CHARS = 1_000_000                 # extracted text per document
MAX_QUESTION_CHARS = 500

CHUNK_TARGET_CHARS = 900                   # size of one searchable chunk
CHUNK_OVERLAP_CHARS = 200                  # last sentence repeated in next chunk

SEARCH_CANDIDATES = 8                      # chunks fetched from PostgreSQL
CHUNKS_USED_FOR_ANSWER = 3
MAX_ANSWER_SENTENCES = 4
MIN_TERM_COVERAGE = 0.34                   # share of question terms a chunk must contain

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".log",
}

NOT_FOUND_MESSAGE = (
    "I couldn't find that in the uploaded documents. "
    "Try rephrasing your question, or ask about a topic the documents cover."
)
NO_DOCUMENTS_MESSAGE = (
    "No documents have been uploaded yet, so I don't have anything to "
    "answer from. Please check back soon."
)
GREETING_MESSAGE = (
    "Hi! I answer questions using the documents our team has uploaded. "
    "What would you like to know?"
)
THANKS_MESSAGE = "You're welcome! Ask me anything else about the documents."

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "am", "do",
    "does", "did", "of", "to", "in", "on", "at", "for", "from", "by", "with",
    "about", "and", "or", "but", "if", "so", "as", "it", "its", "this",
    "that", "these", "those", "i", "me", "my", "we", "our", "you", "your",
    "they", "their", "he", "she", "his", "her", "what", "which", "who",
    "whom", "when", "where", "why", "how", "can", "could", "should",
    "would", "will", "shall", "may", "might", "please", "tell", "give",
    "show", "explain", "need", "want", "know", "there", "any", "some",
    "have", "has", "had", "not", "no", "yes", "than", "then", "into",
    "many", "much", "every", "each", "also", "just", "very", "get", "got",
}


# ======================================================================
# ERRORS
# ======================================================================

class DocumentError(Exception):
    """A problem with an uploaded document that the admin can fix."""


class DuplicateDocumentError(DocumentError):
    """The same text has already been uploaded."""


class UnsupportedFileError(DocumentError):
    """The file type is not supported."""


# ======================================================================
# SCHEMA
# ======================================================================

def ensure_chatbot_tables() -> None:
    """
    Run schema.sql (idempotent). Safe to call on every startup.
    """

    if not SCHEMA_PATH.exists():
        raise RuntimeError(
            f"schema.sql not found next to the application: {SCHEMA_PATH}"
        )

    sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)


# ======================================================================
# TEXT EXTRACTION
# ======================================================================

def clean_text(text: str) -> str:
    """Normalise whitespace and strip characters PostgreSQL rejects."""

    text = text.replace("\x00", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _decode_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return data.decode("latin-1", errors="replace")


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise DocumentError(
            "PDF support needs the 'pypdf' package (pip install pypdf)."
        ) from exc

    try:
        reader = PdfReader(io.BytesIO(data))

        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                raise DocumentError(
                    "This PDF is password protected. Remove the password "
                    "and upload it again."
                )

        pages = [(page.extract_text() or "") for page in reader.pages]

    except DocumentError:
        raise
    except Exception as exc:
        raise DocumentError(f"Could not read this PDF: {exc}") from exc

    return "\n\n".join(pages)


def _extract_docx(data: bytes) -> str:
    try:
        import docx  # python-docx
    except ImportError as exc:
        raise DocumentError(
            "Word support needs the 'python-docx' package "
            "(pip install python-docx)."
        ) from exc

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise DocumentError(f"Could not read this Word file: {exc}") from exc

    parts = [paragraph.text for paragraph in document.paragraphs]

    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    return "\n".join(parts)


def extract_text(filename: str, data: bytes) -> str:
    """
    Return the cleaned plain text of an uploaded file.
    Raises DocumentError (or a subclass) with a message fit for the admin.
    """

    extension = Path(filename or "").suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileError(
            f"'{extension or 'this file type'}' is not supported. "
            f"Upload one of: {', '.join(sorted(SUPPORTED_EXTENSIONS))}."
        )

    if not data:
        raise DocumentError("The uploaded file is empty.")

    if len(data) > MAX_UPLOAD_BYTES:
        raise DocumentError(
            f"File is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )

    if extension == ".pdf":
        raw = _extract_pdf(data)
    elif extension == ".docx":
        raw = _extract_docx(data)
    else:
        raw = _decode_bytes(data)

    text = clean_text(raw)

    if not text:
        raise DocumentError(
            "No readable text was found in this file. If it is a scanned "
            "PDF or an image, run OCR on it first."
        )

    if len(text) > MAX_TEXT_CHARS:
        raise DocumentError(
            f"The document has {len(text):,} characters; "
            f"the limit is {MAX_TEXT_CHARS:,}. Split it into smaller files."
        )

    return text


# ======================================================================
# CHUNKING
# ======================================================================

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def split_sentences(text: str) -> List[str]:
    return [part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip()]


def chunk_text(text: str) -> List[str]:
    """
    Pack sentences into chunks of about CHUNK_TARGET_CHARS characters.
    The last sentence of a chunk is repeated at the start of the next
    one (when short) so an answer that straddles a boundary is not lost.
    """

    units: List[str] = []

    for sentence in split_sentences(text):
        # Hard-split very long unbroken text (tables, minified content).
        while len(sentence) > CHUNK_TARGET_CHARS:
            cut = sentence.rfind(" ", 0, CHUNK_TARGET_CHARS)
            cut = cut if cut > 0 else CHUNK_TARGET_CHARS
            units.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            units.append(sentence)

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for unit in units:
        if current and current_len + len(unit) + 1 > CHUNK_TARGET_CHARS:
            chunks.append(" ".join(current))

            tail = current[-1]
            if len(tail) <= CHUNK_OVERLAP_CHARS:
                current, current_len = [tail], len(tail)
            else:
                current, current_len = [], 0

        current.append(unit)
        current_len += len(unit) + 1

    if current:
        chunks.append(" ".join(current))

    return chunks


# ======================================================================
# DOCUMENT STORAGE
# ======================================================================

_DOCUMENT_COLUMNS = (
    "id, title, filename, content_type, file_size_bytes, "
    "char_count, chunk_count, is_active, created_at"
)


def _document_row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row[0],
        "title": row[1],
        "filename": row[2],
        "content_type": row[3],
        "file_size_bytes": row[4],
        "char_count": row[5],
        "chunk_count": row[6],
        "is_active": row[7],
        "created_at": row[8].isoformat() if row[8] else None,
    }


def add_document(
    title: str,
    text: str,
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Store a document and its searchable chunks in one transaction.
    """

    text = clean_text(text)

    if not text:
        raise DocumentError("The document has no text.")

    title = (title or "").strip()[:200]

    if not title:
        raise DocumentError("A title is required.")

    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    chunks = chunk_text(text)

    if not chunks:
        raise DocumentError("The document has no searchable text.")

    with database_connection() as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                "SELECT id, title FROM chatbot_documents WHERE content_hash = %s;",
                (content_hash,),
            )
            existing = cursor.fetchone()

            if existing:
                raise DuplicateDocumentError(
                    f"This content is already uploaded as "
                    f"'{existing[1]}' (ID {existing[0]})."
                )

            cursor.execute(
                f"""
                INSERT INTO chatbot_documents
                    (title, filename, content_type, file_size_bytes,
                     char_count, chunk_count, content_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING {_DOCUMENT_COLUMNS};
                """,
                (
                    title,
                    (filename or None),
                    (content_type or None),
                    file_size_bytes,
                    len(text),
                    len(chunks),
                    content_hash,
                ),
            )

            document = _document_row_to_dict(cursor.fetchone())

            cursor.executemany(
                """
                INSERT INTO chatbot_chunks (document_id, chunk_index, content)
                VALUES (%s, %s, %s);
                """,
                [
                    (document["id"], index, chunk)
                    for index, chunk in enumerate(chunks)
                ],
            )

    return document


def list_documents() -> List[Dict[str, Any]]:
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {_DOCUMENT_COLUMNS} FROM chatbot_documents "
                "ORDER BY created_at DESC, id DESC;"
            )
            return [_document_row_to_dict(row) for row in cursor.fetchall()]


def set_document_active(document_id: int, is_active: bool) -> Optional[Dict[str, Any]]:
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE chatbot_documents
                SET is_active = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING {_DOCUMENT_COLUMNS};
                """,
                (is_active, document_id),
            )
            row = cursor.fetchone()
            return _document_row_to_dict(row) if row else None


def delete_document(document_id: int) -> bool:
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM chatbot_documents WHERE id = %s;",
                (document_id,),
            )
            return cursor.rowcount > 0


def get_stats() -> Dict[str, int]:
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM chatbot_documents),
                    (SELECT COUNT(*) FROM chatbot_documents WHERE is_active),
                    (SELECT COUNT(*) FROM chatbot_chunks),
                    (SELECT COUNT(*) FROM chatbot_messages),
                    (SELECT COUNT(*) FROM chatbot_messages WHERE NOT matched);
                """
            )
            row = cursor.fetchone()

    return {
        "documents": int(row[0]),
        "active_documents": int(row[1]),
        "chunks": int(row[2]),
        "questions": int(row[3]),
        "unanswered_questions": int(row[4]),
    }


def get_unanswered_questions(limit: int = 50) -> List[Dict[str, Any]]:
    limit = max(1, min(limit, 200))

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT question, created_at
                FROM chatbot_messages
                WHERE NOT matched
                ORDER BY id DESC
                LIMIT %s;
                """,
                (limit,),
            )
            return [
                {"question": row[0], "created_at": row[1].isoformat()}
                for row in cursor.fetchall()
            ]


def has_active_documents() -> bool:
    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM chatbot_documents WHERE is_active);"
            )
            return bool(cursor.fetchone()[0])


# ======================================================================
# RETRIEVAL
# ======================================================================

def _stem(word: str) -> str:
    """Very small stemmer, enough to match 'refunds' with 'refund'."""

    if word.endswith("ss"):          # "process", "access": nothing to strip
        return word

    for suffix in ("ingly", "edly", "ing", "ed", "ly", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def query_terms(question: str) -> List[str]:
    seen: List[str] = []

    for word in re.findall(r"[a-z0-9]+", question.lower()):
        if word in STOPWORDS or len(word) < 2:
            continue
        if word not in seen:
            seen.append(word)

    return seen[:12]


def _term_coverage(terms: List[str], text: str) -> Tuple[int, float]:
    """How many of the question's terms appear in `text` (stem match)."""

    text_stems = {_stem(word) for word in re.findall(r"[a-z0-9]+", text.lower())}
    matched = sum(1 for term in terms if _stem(term) in text_stems)

    return matched, matched / len(terms)


def search_chunks(question: str) -> List[Dict[str, Any]]:
    """
    Best-matching chunks for a question, most relevant first.
    Only chunks of ACTIVE documents are searched.
    """

    terms = query_terms(question)

    if not terms:
        return []

    tsquery = " | ".join(terms)   # terms are [a-z0-9] only: safe for to_tsquery

    with database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    c.id,
                    c.document_id,
                    c.content,
                    d.title,
                    d.filename,
                    ts_rank_cd(c.search_vector, q.query) AS score
                FROM chatbot_chunks c
                JOIN chatbot_documents d
                  ON d.id = c.document_id AND d.is_active
                CROSS JOIN (SELECT to_tsquery('english', %s) AS query) q
                WHERE c.search_vector @@ q.query
                ORDER BY score DESC, c.id ASC
                LIMIT %s;
                """,
                (tsquery, SEARCH_CANDIDATES),
            )
            rows = cursor.fetchall()

    results: List[Dict[str, Any]] = []

    for row in rows:
        matched, coverage = _term_coverage(terms, row[2])

        if matched == 0 or coverage < MIN_TERM_COVERAGE:
            continue

        results.append(
            {
                "chunk_id": row[0],
                "document_id": row[1],
                "content": row[2],
                "title": row[3],
                "filename": row[4],
                "score": float(row[5]),
                "coverage": coverage,
            }
        )

    # Prefer chunks that contain more of the question, then the DB rank.
    results.sort(key=lambda item: (-item["coverage"], -item["score"]))

    return results


# ======================================================================
# ANSWER BUILDING
# ======================================================================

def build_extractive_answer(question: str, chunks: List[Dict[str, Any]]) -> str:
    """
    Pick the sentences that best match the question, straight from the
    documents. Nothing is invented.
    """

    terms = query_terms(question)
    term_stems = {_stem(term) for term in terms}

    candidates: List[Tuple[float, int, int, str]] = []
    seen_sentences = set()

    for chunk_rank, chunk in enumerate(chunks[:CHUNKS_USED_FOR_ANSWER]):
        for position, sentence in enumerate(split_sentences(chunk["content"])):

            key = sentence.lower()
            if key in seen_sentences:
                continue
            seen_sentences.add(key)

            sentence_stems = {
                _stem(word) for word in re.findall(r"[a-z0-9]+", key)
            }
            hits = len(term_stems & sentence_stems)

            if hits == 0:
                continue

            # more matching terms wins; earlier chunk breaks ties
            score = hits - chunk_rank * 0.1
            candidates.append((score, chunk_rank, position, sentence))

    if not candidates:
        # Terms matched the chunk but no single sentence: show the chunk.
        top = chunks[0]["content"]
        return top if len(top) <= 500 else top[:500].rsplit(" ", 1)[0] + "..."

    ranked = sorted(candidates, key=lambda item: -item[0])
    top_score = ranked[0][0]

    # Keep only sentences that match nearly as many question terms as the
    # best sentence, so a stray shared word doesn't add noise.
    ranked = [item for item in ranked if item[0] >= top_score * 0.75]

    # With only a single matching term the evidence is thin: stay short.
    limit = MAX_ANSWER_SENTENCES if top_score >= 2 else 2

    best = ranked[:limit]
    best.sort(key=lambda item: (item[1], item[2]))   # back to reading order

    return " ".join(item[3] for item in best)


def _llm_enabled() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip()) and (
        os.getenv("CHATBOT_USE_LLM", "1").strip() != "0"
    )


def build_llm_answer(question: str, chunks: List[Dict[str, Any]]) -> Optional[str]:
    """
    Optional: let Claude phrase a short answer using ONLY the retrieved
    excerpts. Returns None when it cannot answer or anything fails, in
    which case the caller falls back to the extractive answer.
    """

    import requests

    excerpts = "\n\n".join(
        f"[{index + 1}] ({chunk['title']})\n{chunk['content']}"
        for index, chunk in enumerate(chunks[:CHUNKS_USED_FOR_ANSWER])
    )

    system_prompt = (
        "You answer questions for website visitors using ONLY the document "
        "excerpts provided. Be concise (under 120 words) and friendly. "
        "Never use outside knowledge. If the excerpts do not contain the "
        "answer, reply with exactly: NOT_FOUND"
    )

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": os.getenv("ANTHROPIC_API_KEY", "").strip(),
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": os.getenv("CHATBOT_LLM_MODEL", "claude-haiku-5-5"),
                "max_tokens": 400,
                "system": system_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"Document excerpts:\n{excerpts}\n\n"
                            f"Question: {question}"
                        ),
                    }
                ],
            },
            timeout=20,
        )
        response.raise_for_status()

        blocks = response.json().get("content", [])
        text = "".join(
            block.get("text", "") for block in blocks if block.get("type") == "text"
        ).strip()

        return text or None

    except Exception as exc:
        logger.warning("Chatbot LLM answer failed, using extractive: %s", exc)
        return None


# ======================================================================
# SMALL TALK
# ======================================================================

_GREETING = re.compile(
    r"^\s*(hi|hii+|hello|hey|hola|vanakkam|good\s+(morning|afternoon|evening)|"
    r"how are you|what'?s up)\b[\s!.?]*$",
    re.IGNORECASE,
)
_THANKS = re.compile(
    r"^\s*(thanks|thank you|thx|ok thanks|okay thanks|bye|goodbye)\b[\s!.?]*$",
    re.IGNORECASE,
)


def _small_talk_reply(question: str) -> Optional[str]:
    if _GREETING.match(question):
        return GREETING_MESSAGE
    if _THANKS.match(question):
        return THANKS_MESSAGE
    return None


# ======================================================================
# PUBLIC ENTRY POINT
# ======================================================================

def _log_message(
    session_id: Optional[str],
    question: str,
    answer: str,
    matched: bool,
    top_document_id: Optional[int],
) -> None:
    """Logging must never break a chat reply."""

    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO chatbot_messages
                        (session_id, question, answer, matched, top_document_id)
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (
                        (session_id or None) and session_id[:64],
                        question,
                        answer,
                        matched,
                        top_document_id,
                    ),
                )
    except Exception as exc:
        logger.warning("Could not log chatbot message: %s", exc)


def answer_question(question: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Answer one visitor question from the uploaded documents.

    Returns:
        {"answer": str, "matched": bool, "sources": [{"document_id", "title"}]}
    """

    question = clean_text(question)[:MAX_QUESTION_CHARS]

    if not question:
        return {"answer": "Please type a question.", "matched": False, "sources": []}

    small_talk = _small_talk_reply(question)

    if small_talk:
        return {"answer": small_talk, "matched": True, "sources": []}

    if not has_active_documents():
        return {"answer": NO_DOCUMENTS_MESSAGE, "matched": False, "sources": []}

    chunks = search_chunks(question)

    if not chunks:
        _log_message(session_id, question, NOT_FOUND_MESSAGE, False, None)
        return {"answer": NOT_FOUND_MESSAGE, "matched": False, "sources": []}

    answer: Optional[str] = None

    if _llm_enabled():
        answer = build_llm_answer(question, chunks)

        if answer and answer.strip().upper().startswith("NOT_FOUND"):
            _log_message(session_id, question, NOT_FOUND_MESSAGE, False, None)
            return {"answer": NOT_FOUND_MESSAGE, "matched": False, "sources": []}

    if not answer:
        answer = build_extractive_answer(question, chunks)

    sources: List[Dict[str, Any]] = []
    seen_documents = set()

    for chunk in chunks[:CHUNKS_USED_FOR_ANSWER]:
        if chunk["document_id"] not in seen_documents:
            seen_documents.add(chunk["document_id"])
            sources.append(
                {"document_id": chunk["document_id"], "title": chunk["title"]}
            )

    _log_message(session_id, question, answer, True, chunks[0]["document_id"])

    return {"answer": answer, "matched": True, "sources": sources}
