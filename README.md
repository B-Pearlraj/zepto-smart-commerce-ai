# Portfolio AI Assistant (RAG on Neon pgvector)

A floating chat assistant for your portfolio site that answers **only** from documents you upload in an admin page.

```
Visitor's browser (your portfolio)            Render web service (this folder)              Neon + Gemini
-----------------------------------           ----------------------------------           ----------------------
chatbot.js  --POST /api/chat--------------->  main.py -> rag.py --embed question------->   Gemini embeddings
                                                          |      --vector search------->   Neon: kb_chunks (pgvector)
                                                          '--- answer from chunks only->   Gemini chat model

You, at https://<service>.onrender.com/admin
admin.html --upload PDF/DOCX/TXT--> main.py -> ingest.py: extract -> chunk -> embed ---->   Neon: kb_documents + kb_chunks
```

This is a **separate service** from your Zepto backend, so nothing in `main.py`, `database*.py` or `app.py` of the Zepto project is touched.

## 1. Folder structure

Put this folder in its **own new GitHub repository** (recommended; the Zepto repo also has a `main.py` and auto-deploys on every commit, so mixing them would cause conflicts).

```
ai-assistant/                  <- repo root (Render "Root Directory" stays empty)
  main.py                      FastAPI app: chat, admin, documents API
  config.py                    environment variables and limits
  db.py                        Neon connection + schema runner
  schema.sql                   tables + pgvector index
  llm.py                       Gemini embeddings and chat calls
  ingest.py                    extract -> chunk -> embed -> store
  rag.py                       retrieval + grounded answer + scope rules
  security.py                  admin session cookie, rate limiting
  check_setup.py               one-command configuration test
  requirements.txt  render.yaml  .env.example  .gitignore
  static/
    admin.html                 admin dashboard   (served at /admin)
    chatbot.js  chatbot.css    the widget        (served at /static/...)
```

Your portfolio repo gets only `chatbot.js` and `chatbot.css` (copied next to `index.html`) plus two lines in `index.html` (`index-snippet.html`).

## 2. Neon setup

You already enabled pgvector. Remaining steps:

1. **Use the database you want.** Either a new Neon project for the portfolio (cleanest) or the existing one: all tables here start with `kb_`, so they do not collide with the Zepto `orders` table.
2. **Get the connection string:** Neon Dashboard -> **Connect** -> copy the connection string (it looks like `postgresql://user:password@ep-...-pooler....neon.tech/neondb?sslmode=require`). The pooled one is fine.
3. **Create the tables.** Either:
   - do nothing: the app runs `schema.sql` automatically on every start (safe to repeat), or
   - paste `schema.sql` into Neon **SQL Editor** and run it.
4. After the first deploy, Neon -> **Tables** should list `kb_documents`, `kb_chunks`, `kb_chat_log`.

**Keeping credentials secure**
- The connection string and API keys exist only as **Render environment variables** (or a local `.env`, which `.gitignore` excludes). They never appear in code or in the browser.
- The browser only talks to `/api/chat`. It cannot read the database or the documents.
- The admin API requires a signed, HttpOnly, SameSite=Strict cookie that expires after 8 hours.

## 3. Gemini API key

Create a key at https://aistudio.google.com/apikey. It is used for embeddings (`gemini-embedding-001`, 768 dimensions) and for answers (`gemini-2.5-flash`). Both model names are environment variables (`GEMINI_EMBED_MODEL`, `GEMINI_CHAT_MODEL`), so if Google renames or retires one you only change a setting. If you change the embedding model or `EMBED_DIM`, you must also change `vector(768)` in `schema.sql`, recreate `kb_chunks`, and re-upload your documents.

## 4. Environment variables

| Variable | Required | Meaning |
|---|---|---|
| `DATABASE_URL` | yes | Neon connection string |
| `GEMINI_API_KEY` | yes | Google AI Studio key |
| `ADMIN_PASSWORD` | yes | Password for `/admin` (long and unique) |
| `SECRET_KEY` | yes | Random 48+ characters; signs admin sessions |
| `ALLOWED_ORIGINS` | yes | Your portfolio URL(s), comma separated, **no trailing slash**, e.g. `https://pearl-techlab.onrender.com` |
| `OWNER_NAME` | no | Name used in the assistant's prompt (default `Muthuraj B`) |
| `MIN_SCORE` | no | Relevance threshold, default `0.40` |
| `PYTHON_VERSION` | no | `3.12.7` recommended on Render |

More optional limits (upload size, rate limits, chunk size) are listed in `.env.example`.

## 5. Deploy on Render

1. Push this folder to a new GitHub repo.
2. Render -> **New** -> **Web Service** -> connect that repo.
3. Settings:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*"`
   - **Health Check Path:** `/health`
4. **Environment** tab: add the variables from section 4.
5. Deploy. In the logs look for `Database schema is ready.`
6. Open `https://<your-service>.onrender.com/health?deep=1`. You want `"database_connected": true` and `"pgvector_enabled": true`.

(`render.yaml` is an optional Blueprint that pre-fills these settings.)

Free instances sleep after ~15 minutes without traffic. The first request afterwards can take up to a minute; the widget shows a "waking up" notice and pre-warms the service when a visitor hovers or opens the chat button.

## 6. Add the widget to your portfolio

1. Copy `static/chatbot.css` and `static/chatbot.js` next to your `index.html`.
2. Add the two snippets from `index-snippet.html` (stylesheet in `<head>`, script before `</body>`), setting `data-api` to your Render URL and `data-logo` to your logo image.
3. Redeploy the portfolio.

Nothing else in your page changes. The widget builds its own elements inside one container (`#pa-root`), every CSS rule is scoped to it, and it follows your light/dark toggle automatically (it reads the page's background colour and re-checks whenever the page's attributes change). `window.PearlAssistant.open()` opens the chat from any of your own buttons if you want that later.

## 7. Upload and manage documents

1. Open `https://<your-service>.onrender.com/admin` and sign in with `ADMIN_PASSWORD`.
2. Drop a PDF, DOCX, TXT or MD file (max 10 MB), optionally give it a title, click **Upload and process**.
3. The status goes `processing` -> `ready` (seconds to a minute). `failed` shows the reason (for example, a scanned PDF with no text layer).
4. **View chunks** shows exactly what was stored. **Delete** removes the document and all its vectors.
5. Uploading the exact same file twice is rejected. To replace a document, delete the old one and upload the new one.

Tips for good answers: use clear headings and full sentences ("Project: Zepto Smart Commerce AI. Built with FastAPI, Streamlit ... Result: ..."), one topic per document (CV, project details, services), and keep information current by deleting outdated files.

## 8. Test and verify

**Configuration:** in the Render **Shell** tab (or locally with a `.env`) run `python check_setup.py`. It checks the environment variables, the database, pgvector, the tables, the embedding call and the chat model.

**Retrieval:** in `/admin` -> **Test the assistant**:
1. Type "What projects have you developed?" and click **Show retrieved passages**. The passages should come from your documents with scores clearly above `0.40`.
2. Type "What is today's weather?". Scores should be low and flagged red.
3. Click **Ask assistant** for both. Expected: project details for the first; for the second exactly *"I'm sorry, but I can only assist with questions related to the available documents, projects, professional experience, and services."*
4. Ask about something work-related that is not in your files (for example a technology you never mentioned). Expected: *"...that information isn't available in my knowledge base."*

**Tuning:** if good questions are refused, lower `MIN_SCORE` (try `0.35`). If unrelated questions get through to the model, raise it (try `0.45`). Use the score display to choose.

**On the live site:** open the widget and repeat the same questions. To see what visitors ask and what could not be answered, run in Neon's SQL Editor:
```sql
SELECT asked_at, outcome, round(top_score::numeric, 2) AS score, question
FROM kb_chat_log ORDER BY asked_at DESC LIMIT 50;
```

## 9. How the restrictions work

1. **Similarity gate:** if no stored passage is close enough to the question, the fixed out-of-scope sentence is returned and the language model is never called.
2. **Strict prompt:** the model may use only the retrieved passages. It must answer `NOT_IN_KB` (mapped to the "not available" message) or `OUT_OF_SCOPE` (mapped to the sorry message) otherwise.
3. **Prompt-injection hardening:** instructions live in a separate system message; document text, chat history and the question are wrapped in delimiter tags, treated as untrusted data, and any attempt to forge those tags is neutralised; the question is length-limited; chat history is accepted only as plain text.
4. **Output safety:** the widget HTML-escapes everything before showing it.
5. **Abuse limits:** per-IP limits (10/min, 100/day), a site-wide daily cap of 600 chats (protects your API quota), admin login lockout after 5 failures per 15 minutes, uploads restricted to PDF/DOCX/TXT/MD with content checks and a size limit, and no public API docs.

No prompt-based defence is absolute; the gate and strict prompt make off-topic answers rare, not impossible, so spot-check with the admin test box.

## 10. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Chat shows "I couldn't reach the assistant" | `data-api` wrong; service asleep (wait a minute and retry); or `ALLOWED_ORIGINS` doesn't exactly match your site (open the browser console: a CORS error means it doesn't; no trailing slash, `https://` vs `http://`, `www.` matter) |
| `/health?deep=1` -> `database_connected: false` | Wrong `DATABASE_URL` (copy it again from Neon), or Neon is waking (retry); check Render logs for the error type |
| `pgvector_enabled: false` | Run `CREATE EXTENSION IF NOT EXISTS vector;` in the Neon SQL Editor |
| Upload stays `processing` | Wait up to a minute; after 10 minutes it is marked `failed`. Check Render logs for Gemini errors |
| Upload `failed`: "No readable text" | Scanned/image PDF (no OCR). Export a text version or use DOCX/TXT |
| Gemini error 400/404 mentioning model | Model name retired or renamed: set `GEMINI_CHAT_MODEL` / `GEMINI_EMBED_MODEL` in Render |
| Gemini error 429 | Free-tier quota reached; wait, or enable billing in Google AI Studio |
| "Embedding has N dimensions, expected 768" | `EMBED_DIM` and `vector(768)` disagree; make them match, recreate `kb_chunks`, re-upload |
| Admin login always fails | `ADMIN_PASSWORD` not set or has trailing spaces; after 5 failures wait 15 minutes. On plain `http://localhost` set `COOKIE_SECURE=false` |
| Admin logged out after each deploy | `SECRET_KEY` not set (a random one is generated at every start) |
| Good questions get the "sorry" message | Lower `MIN_SCORE`; check the documents actually contain the information (View chunks) |
| Answers look incomplete | Raise `TOP_K` (e.g. 8) or split very long documents by topic |
| Widget colours look wrong after toggling theme | Hard refresh; or force a theme with `data-theme="dark"` on the script tag |
