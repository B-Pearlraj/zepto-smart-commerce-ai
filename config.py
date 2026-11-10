"""
Central configuration. Everything comes from environment variables so that
no secret is ever written in code (set them in the Render dashboard; use a
local .env file only for testing).
"""

import os
import secrets
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("assistant.config")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


# --------------------------------------------------------------------------
# Required secrets
# --------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# Signs admin session cookies. If missing, a random key is generated at boot
# (works, but every restart logs the admin out).
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(48)
    logger.warning("SECRET_KEY is not set; using a temporary random key.")

# --------------------------------------------------------------------------
# Models (override in Render if Google renames/retires a model)
# --------------------------------------------------------------------------
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash").strip()
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001").strip()

# Must match vector(N) in schema.sql. Changing it later means re-creating
# kb_chunks and re-uploading every document.
EMBED_DIM = _int("EMBED_DIM", 768)

# --------------------------------------------------------------------------
# Site / CORS / admin
# --------------------------------------------------------------------------
OWNER_NAME = os.getenv("OWNER_NAME", "Muthuraj B").strip()

# Comma-separated list of sites allowed to call /api/chat, with no trailing
# slash, e.g. "https://pearl-techlab.onrender.com,http://localhost:5500"
ALLOWED_ORIGINS = [
    o.strip().rstrip("/")
    for o in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]

COOKIE_SECURE = _bool("COOKIE_SECURE", True)  # set false only for http://localhost
SESSION_HOURS = _int("SESSION_HOURS", 8)

# --------------------------------------------------------------------------
# Ingestion limits
# --------------------------------------------------------------------------
MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 10)
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
CHUNK_SIZE = _int("CHUNK_SIZE", 900)          # characters
CHUNK_OVERLAP = _int("CHUNK_OVERLAP", 150)    # characters
MAX_CHUNKS_PER_DOC = _int("MAX_CHUNKS_PER_DOC", 600)
EMBED_BATCH_SIZE = _int("EMBED_BATCH_SIZE", 25)

# --------------------------------------------------------------------------
# Retrieval / answering
# --------------------------------------------------------------------------
TOP_K = _int("TOP_K", 5)
# Cosine similarity (0..1). Chunks scoring below this are treated as "not
# about the knowledge base". Tune with the "Test retrieval" box in /admin.
MIN_SCORE = _float("MIN_SCORE", 0.40)
MAX_QUESTION_CHARS = _int("MAX_QUESTION_CHARS", 600)
MAX_OUTPUT_TOKENS = _int("MAX_OUTPUT_TOKENS", 1024)

# --------------------------------------------------------------------------
# Abuse protection
# --------------------------------------------------------------------------
CHAT_RATE_PER_MIN = _int("CHAT_RATE_PER_MIN", 10)    # per visitor IP
CHAT_RATE_PER_DAY = _int("CHAT_RATE_PER_DAY", 100)   # per visitor IP
CHAT_GLOBAL_PER_DAY = _int("CHAT_GLOBAL_PER_DAY", 600)  # whole site (protects API quota)
LOGIN_MAX_FAILURES = _int("LOGIN_MAX_FAILURES", 5)   # per IP per 15 minutes
