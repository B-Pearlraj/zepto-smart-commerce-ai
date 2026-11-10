"""
Admin authentication (signed, expiring session cookie) and in-memory rate
limiting. No extra dependencies: only the Python standard library.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from config import ADMIN_PASSWORD, SECRET_KEY, SESSION_HOURS

COOKIE_NAME = "kb_admin"
COOKIE_PATH = "/api/admin"


# ----------------------------------------------------------------------------
# Admin session token:  base64(json payload) . base64(HMAC-SHA256 signature)
# ----------------------------------------------------------------------------
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(body: str) -> str:
    return _b64(hmac.new(SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest())


def make_token() -> str:
    payload = {"exp": int(time.time()) + SESSION_HOURS * 3600, "n": secrets.token_hex(8)}
    body = _b64(json.dumps(payload).encode())
    return f"{body}.{_sign(body)}"


def verify_token(token: str) -> bool:
    try:
        body, signature = token.split(".", 1)
        if not hmac.compare_digest(signature, _sign(body)):
            return False
        return json.loads(_unb64(body)).get("exp", 0) > time.time()
    except Exception:
        return False


def check_password(candidate: str) -> bool:
    if not ADMIN_PASSWORD:
        return False
    # Hash both sides so the comparison time does not depend on length.
    return hmac.compare_digest(
        hashlib.sha256(candidate.encode()).digest(),
        hashlib.sha256(ADMIN_PASSWORD.encode()).digest(),
    )


def require_admin(request: Request) -> None:
    """FastAPI dependency: 401 unless a valid admin cookie is present."""
    if not ADMIN_PASSWORD:
        raise HTTPException(503, "Admin access is disabled: ADMIN_PASSWORD is not set.")

    token = request.cookies.get(COOKIE_NAME, "")
    if not token or not verify_token(token):
        raise HTTPException(401, "Please sign in.")


# ----------------------------------------------------------------------------
# Rate limiting (per process; fine for a single Render instance)
# ----------------------------------------------------------------------------
class RateLimiter:
    def __init__(self):
        self._hits = defaultdict(deque)

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()

        if len(self._hits) > 5000:  # keep memory bounded
            self._hits.clear()

        hits = self._hits[key]
        while hits and hits[0] <= now - window_seconds:
            hits.popleft()

        if len(hits) >= limit:
            return False

        hits.append(now)
        return True

    def count(self, key: str, window_seconds: int) -> int:
        now = time.time()
        hits = self._hits.get(key)
        if not hits:
            return 0
        return sum(1 for t in hits if t > now - window_seconds)


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    # uvicorn runs with --proxy-headers, so this is the real visitor IP on Render.
    return request.client.host if request.client else "unknown"
