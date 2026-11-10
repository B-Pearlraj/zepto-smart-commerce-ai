"""
Thin client for the Gemini REST API: embeddings and answer generation.
Uses plain `requests`, so there is no heavy SDK and no local ML model
(important for Render's small free instances).
"""

import logging
import time

import requests

from config import (
    EMBED_BATCH_SIZE,
    EMBED_DIM,
    GEMINI_API_KEY,
    GEMINI_CHAT_MODEL,
    GEMINI_EMBED_MODEL,
    MAX_OUTPUT_TOKENS,
)

logger = logging.getLogger("assistant.llm")

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
RETRY_STATUS = (429, 500, 502, 503, 504)


class LLMError(RuntimeError):
    """Raised when the Gemini API cannot be reached or returns an error."""


def _error_message(response: requests.Response) -> str:
    try:
        return response.json().get("error", {}).get("message") or response.text[:300]
    except Exception:
        return response.text[:300]


def _post(path: str, body: dict, timeout: int = 60, retries: int = 4) -> dict:
    if not GEMINI_API_KEY:
        raise LLMError("GEMINI_API_KEY is not configured.")

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,  # header, so the key never appears in logs/URLs
    }

    for attempt in range(retries):
        last_attempt = attempt == retries - 1

        try:
            response = requests.post(
                f"{BASE_URL}/{path}", json=body, headers=headers, timeout=timeout
            )
        except requests.RequestException as exc:
            if last_attempt:
                raise LLMError(f"Could not reach the Gemini API: {type(exc).__name__}") from exc
            time.sleep(2 ** attempt)
            continue

        if response.status_code in RETRY_STATUS and not last_attempt:
            time.sleep(min(2 ** (attempt + 1), 20))
            continue

        if response.status_code >= 400:
            raise LLMError(f"Gemini API error {response.status_code}: {_error_message(response)}")

        return response.json()

    raise LLMError("Gemini API request failed.")


# ----------------------------------------------------------------------------
# Embeddings
# ----------------------------------------------------------------------------
def embed_texts(texts: list, task_type: str = "RETRIEVAL_DOCUMENT") -> list:
    """Return one embedding (list of floats) per input text, in order."""
    embeddings = []

    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start:start + EMBED_BATCH_SIZE]

        requests_body = [
            {
                "model": f"models/{GEMINI_EMBED_MODEL}",
                "content": {"parts": [{"text": text}]},
                "taskType": task_type,
                "outputDimensionality": EMBED_DIM,
            }
            for text in batch
        ]

        data = _post(
            f"models/{GEMINI_EMBED_MODEL}:batchEmbedContents",
            {"requests": requests_body},
        )

        returned = data.get("embeddings") or []
        if len(returned) != len(batch):
            raise LLMError("The embedding service returned an unexpected number of vectors.")

        for item in returned:
            values = item.get("values") or []
            if len(values) != EMBED_DIM:
                raise LLMError(
                    f"Embedding has {len(values)} dimensions, expected {EMBED_DIM}. "
                    "Check EMBED_DIM and vector(N) in schema.sql."
                )
            embeddings.append(values)

        if start + EMBED_BATCH_SIZE < len(texts):
            time.sleep(0.5)  # stay polite with free-tier rate limits

    return embeddings


def embed_query(text: str) -> list:
    return embed_texts([text], task_type="RETRIEVAL_QUERY")[0]


# ----------------------------------------------------------------------------
# Generation
# ----------------------------------------------------------------------------
def generate(system_prompt: str, user_content: str) -> str:
    """Return the model's text reply ('' if the model returned nothing)."""
    generation_config = {
        "temperature": 0.2,
        "maxOutputTokens": MAX_OUTPUT_TOKENS,
    }

    # Gemini 2.5 Flash "thinks" by default, which is slower and eats output
    # tokens. Document Q&A does not need it.
    if "2.5-flash" in GEMINI_CHAT_MODEL:
        generation_config["thinkingConfig"] = {"thinkingBudget": 0}

    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        "generationConfig": generation_config,
    }

    data = _post(f"models/{GEMINI_CHAT_MODEL}:generateContent", body, timeout=60)

    candidates = data.get("candidates") or []
    if not candidates:
        logger.warning("Gemini returned no candidates: %s", data.get("promptFeedback"))
        return ""

    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(part.get("text", "") for part in parts).strip()
