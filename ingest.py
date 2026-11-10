"""
Document ingestion pipeline:

    uploaded file -> extract text -> clean -> split into chunks
                  -> embed every chunk -> store text + vectors in Neon

Used by the admin upload endpoint (runs as a background task), and it can
also be run from the command line for a local file:

    python ingest.py path/to/cv.pdf "My CV"
"""

import hashlib
import io
import logging
import re
import sys
from pathlib import Path

from config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    MAX_CHUNKS_PER_DOC,
)
from db import connection, to_vector_literal
from llm import embed_texts

logger = logging.getLogger("assistant.ingest")

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


class IngestError(ValueError):
    """A problem with the uploaded file that the admin can understand and fix."""


# ----------------------------------------------------------------------------
# 1. Validation
# ----------------------------------------------------------------------------
def file_extension(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def validate_file(filename: str, data: bytes) -> str:
    """Check extension and magic bytes. Returns the extension without the dot."""
    ext = file_extension(filename)

    if ext not in ALLOWED_EXTENSIONS:
        raise IngestError("Unsupported file type. Upload a PDF, DOCX, TXT or MD file.")

    if not data:
        raise IngestError("The file is empty.")

    if ext == ".pdf" and not data.startswith(b"%PDF"):
        raise IngestError("This file is not a valid PDF.")

    if ext == ".docx" and not data.startswith(b"PK"):
        raise IngestError("This file is not a valid DOCX (Word 2007+) document.")

    return ext.lstrip(".")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ----------------------------------------------------------------------------
# 2. Text extraction
# ----------------------------------------------------------------------------
def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))

        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                raise IngestError("This PDF is password-protected.")

        pages = [(page.extract_text() or "") for page in reader.pages]
    except IngestError:
        raise
    except Exception as exc:
        raise IngestError(f"The PDF could not be read ({type(exc).__name__}).") from exc

    return "\n\n".join(pages)


def _extract_docx(data: bytes) -> str:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:
        raise IngestError(f"The DOCX could not be read ({type(exc).__name__}).") from exc

    parts = []

    # Walk the body in document order so tables stay next to their headings.
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]

        if tag == "p":
            parts.append(Paragraph(child, document).text)

        elif tag == "tbl":
            table = Table(child, document)
            for row in table.rows:
                cells = []
                for cell in row.cells:
                    text = cell.text.strip()
                    if text and (not cells or cells[-1] != text):  # skip merged-cell repeats
                        cells.append(text)
                if cells:
                    parts.append(" | ".join(cells))

    return "\n".join(parts)


def _extract_plain(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def extract_text(filename: str, data: bytes) -> str:
    ext = file_extension(filename)

    if ext == ".pdf":
        text = _extract_pdf(data)
    elif ext == ".docx":
        text = _extract_docx(data)
    else:
        text = _extract_plain(data)

    text = clean_text(text)

    if len(text) < 20:
        raise IngestError(
            "No readable text was found. Scanned/image-only PDFs are not supported "
            "(there is no OCR); upload a text-based file instead."
        )

    return text


def clean_text(text: str) -> str:
    text = text.replace("\x00", "")                 # PostgreSQL rejects NUL characters
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ----------------------------------------------------------------------------
# 3. Chunking
# ----------------------------------------------------------------------------
def _units(text: str):
    """Yield paragraph-sized pieces, splitting oversized paragraphs by sentence."""
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        if len(paragraph) <= CHUNK_SIZE:
            yield paragraph
            continue

        for sentence in re.split(r"(?<=[.!?])\s+|\n", paragraph):
            sentence = sentence.strip()
            while len(sentence) > CHUNK_SIZE:        # no punctuation at all: hard split
                yield sentence[:CHUNK_SIZE]
                sentence = sentence[CHUNK_SIZE:]
            if sentence:
                yield sentence


def chunk_text(text: str) -> list:
    """
    Pack paragraphs/sentences into chunks of roughly CHUNK_SIZE characters,
    repeating the last ~CHUNK_OVERLAP characters at the start of the next
    chunk so an idea that straddles a boundary is not lost.
    """
    chunks, current, size = [], [], 0

    for unit in _units(text):
        if current and size + len(unit) + 2 > CHUNK_SIZE:
            chunks.append("\n\n".join(current))

            tail, tail_size = [], 0
            for previous in reversed(current):
                if tail_size + len(previous) > CHUNK_OVERLAP:
                    break
                tail.insert(0, previous)
                tail_size += len(previous) + 2

            current, size = tail, tail_size

        current.append(unit)
        size += len(unit) + 2

    if current:
        chunks.append("\n\n".join(current))

    return [chunk for chunk in chunks if len(chunk.strip()) >= 20]


# ----------------------------------------------------------------------------
# 4. Store
# ----------------------------------------------------------------------------
def create_document_record(title: str, filename: str, file_type: str, size: int, content_hash: str) -> int:
    """Insert a 'processing' row. Raises psycopg.errors.UniqueViolation on a duplicate file."""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO kb_documents (title, filename, file_type, file_size_bytes, content_hash)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (title, filename, file_type, size, content_hash),
            )
            return cur.fetchone()[0]


def _mark_failed(document_id: int, message: str) -> None:
    try:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE kb_documents
                       SET status = 'failed', error_message = %s, updated_at = CURRENT_TIMESTAMP
                     WHERE id = %s
                    """,
                    (message[:500], document_id),
                )
    except Exception:
        logger.exception("Could not mark document %s as failed", document_id)


def process_document(document_id: int, title: str, filename: str, data: bytes) -> None:
    """
    Full pipeline for one stored document record. Never raises: success or
    failure is written to kb_documents.status so the admin page can show it.
    """
    try:
        text = extract_text(filename, data)
        chunks = chunk_text(text)

        if not chunks:
            raise IngestError("The document did not produce any usable text chunks.")

        if len(chunks) > MAX_CHUNKS_PER_DOC:
            raise IngestError(
                f"The document is too large ({len(chunks)} chunks; the limit is "
                f"{MAX_CHUNKS_PER_DOC}). Split it into smaller files."
            )

        # Prefix the title so every vector "knows" which document it came from.
        vectors = embed_texts([f"{title}\n\n{chunk}" for chunk in chunks])

        rows = [
            (document_id, index, chunk, to_vector_literal(vector))
            for index, (chunk, vector) in enumerate(zip(chunks, vectors))
        ]

        # One transaction: chunks and 'ready' status appear together or not at all.
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM kb_chunks WHERE document_id = %s", (document_id,))
                cur.executemany(
                    """
                    INSERT INTO kb_chunks (document_id, chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s::vector)
                    """,
                    rows,
                )
                cur.execute(
                    """
                    UPDATE kb_documents
                       SET status = 'ready', error_message = NULL,
                           char_count = %s, chunk_count = %s, updated_at = CURRENT_TIMESTAMP
                     WHERE id = %s
                    """,
                    (len(text), len(chunks), document_id),
                )

        logger.info("Document %s ingested: %s chunks, %s characters", document_id, len(chunks), len(text))

    except IngestError as exc:
        logger.warning("Document %s rejected: %s", document_id, exc)
        _mark_failed(document_id, str(exc))

    except Exception as exc:
        logger.exception("Document %s failed", document_id)
        _mark_failed(document_id, f"Processing failed: {exc}")


# ----------------------------------------------------------------------------
# Command-line use
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python ingest.py <file> [title]")
        sys.exit(1)

    path = Path(sys.argv[1])
    file_bytes = path.read_bytes()
    doc_title = sys.argv[2] if len(sys.argv) > 2 else path.stem

    kind = validate_file(path.name, file_bytes)

    from db import init_schema

    init_schema()
    new_id = create_document_record(doc_title, path.name, kind, len(file_bytes), sha256_hex(file_bytes))
    process_document(new_id, doc_title, path.name, file_bytes)
    print(f"Done. Document id = {new_id}")
