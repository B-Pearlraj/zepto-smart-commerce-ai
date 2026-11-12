# Zepto Smart Commerce AI — Additive Document RAG Upgrade

This package preserves the supplied FastAPI prediction/order routes and Streamlit order chat, and adds a **separate document assistant**. The original uploaded files are not modified. Other backend modules referenced by `main.py` (`inference.py`, `config.py`, `schemas.py`, `weather_provider.py`, `tomtom_traffic_provider.py`, model assets, etc.) were not uploaded and **must remain in your existing repository**.

## Deployment

1. Copy `main.py`, `chatbot_routes.py`, `rag.py`, `ingest.py`, `admin.html`, `database.py`, and the updated `requirements.txt` into your **existing FastAPI backend repository**. Preserve your other existing files. Copy `app.py` to your **Streamlit frontend repository** as the app entry point, preserving its other assets. The other included files are preserved copies for reference; do not overwrite newer repository versions blindly.
2. On the Render **FastAPI backend** environment, retain your existing `DATABASE_URL`, `ADMIN_TOKEN`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `MIN_SCORE`, `OPENWEATHER_API_KEY`, and `TOMTOM_API_KEY`. Set `EMBEDDING_MODEL=text-embedding-3-small` and `EMBEDDING_DIM=1536` if your LLM provider supports OpenAI-compatible embeddings. **A chat completion endpoint alone is insufficient: embeddings must be supported by the provider.** If using a different embedding model, configure its actual dimension before initializing tables. Do not expose admin token or LLM keys to the browser widget or Streamlit users.
3. Redeploy FastAPI. Open `https://zepto-smart-commerce-ai.onrender.com/rag/admin`, enter your token and click **Initialize vector tables**. This creates `rag_documents` and `rag_chunks` alongside existing `orders` and `prediction_audit`. No existing tables are dropped.
4. Upload a supported text PDF, DOCX, TXT or MD document from the admin page. It is extracted, chunked with overlap, embedded, and stored in Neon. For scanned/image-only PDFs, first run OCR externally.
5. Verify `POST /rag/chat` with `{"question":"What does the uploaded document describe?"}`. The chatbot returns `answer` and `sources`. If nothing matches, it refuses to invent a document answer.
6. Redeploy the Streamlit frontend with the new `app.py`. The existing order prediction chat remains intact; the new document assistant appears in a separate expandable section.

## Optional HTML widget

`chatbot.js` and `chatbot.css` are for a **normal HTML website**, not a native Streamlit widget. Add this to an HTML page:

```html
<script src="/chatbot.js" data-api="https://zepto-smart-commerce-ai.onrender.com" defer></script>
```

Host the JS and CSS on the same static site. For cross-origin HTML usage, configure FastAPI CORS for the exact allowed website origin; **do not use wildcard origins for privileged admin endpoints**. The included Streamlit integration does not require browser-side CORS because it calls FastAPI from Python.

## Security / operational notes

- Upload, initialize, list, and delete operations require `Authorization: Bearer <ADMIN_TOKEN>`. Public chat never receives the token.
- The admin page is served from the backend origin so browser uploads are same-origin. It stores no token persistently.
- Never publish admin credentials, Neon connection strings, or API keys. Rotate them if exposed.
- Uploaded files are not retained as files; extracted text and vectors are stored in Neon. Delete removes both document and chunks.
- This starter uses exact vector similarity search; for large document collections add an appropriate pgvector index and evaluate retrieval quality.
- `MIN_SCORE` is a tunable heuristic, not a guarantee of relevance. Answers are LLM-generated and should be checked against cited documents.
- For a publicly accessible deployment, add per-IP/user rate limiting and usage quotas to `/rag/chat` to protect LLM spend. Add admin audit logging and authentication hardening as needed.
- `LLM_BASE_URL` must point to a compatible API base (usually ending in `/v1`), not a chat-completions URL.
- The uploaded backend `main.py` depends on other modules that were not supplied; full end-to-end deployment cannot be tested here.
