"""
Run this once after setting your environment variables (locally, or in the
Render Shell tab) to find configuration problems quickly:

    python check_setup.py
"""
import sys

from config import ADMIN_PASSWORD, DATABASE_URL, EMBED_DIM, GEMINI_API_KEY


def line(ok, text):
    print(("  [ OK ] " if ok else "  [FAIL] ") + text)
    return ok


def main():
    results = []
    print("\nEnvironment")
    results.append(line(bool(DATABASE_URL), "DATABASE_URL is set"))
    results.append(line(bool(GEMINI_API_KEY), "GEMINI_API_KEY is set"))
    results.append(line(bool(ADMIN_PASSWORD), "ADMIN_PASSWORD is set"))

    print("\nDatabase")
    try:
        from db import connection, init_schema

        init_schema()
        with connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT extname FROM pg_extension WHERE extname='vector'")
            results.append(line(cur.fetchone() is not None, "pgvector extension is enabled"))
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name LIKE 'kb_%' ORDER BY 1"
            )
            tables = [r[0] for r in cur.fetchall()]
            for t in ("kb_chat_log", "kb_chunks", "kb_documents"):
                results.append(line(t in tables, f"table {t} exists"))
    except Exception as exc:
        results.append(line(False, f"database check failed: {type(exc).__name__}: {exc}"))

    print("\nEmbeddings")
    try:
        from llm import embed_query

        vector = embed_query("connection test")
        results.append(line(len(vector) == EMBED_DIM, f"embedding returned {len(vector)} dimensions (expected {EMBED_DIM})"))
    except Exception as exc:
        results.append(line(False, f"embedding call failed: {exc}"))

    print("\nChat model")
    try:
        from llm import generate

        reply = generate("Reply with the single word: ok", "ping")
        results.append(line(bool(reply), f"model replied: {reply[:40]!r}"))
    except Exception as exc:
        results.append(line(False, f"chat model call failed: {exc}"))

    print("\nAll checks passed." if all(results) else "\nSome checks failed. See the messages above.")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
