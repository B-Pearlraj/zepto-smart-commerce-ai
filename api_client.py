from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# (connect timeout, read timeout) in seconds.
# Generous because a sleeping Render service can need 30-60 seconds
# to wake up, and Neon may need a few more seconds after that.
DEFAULT_TIMEOUT = (10, 60)
PREDICT_TIMEOUT = (10, 90)

# The sidebar status check must never freeze the page, so it uses
# short timeouts and no retries.
PING_TIMEOUT = (3, 8)


class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

        # One shared session: reuses connections and retries
        # transient errors (rate limit / cold start / database waking up).
        self.session = requests.Session()

        retry = Retry(
            total=3,
            backoff_factor=1.5,
            status_forcelist=(429, 502, 503, 504),
            allowed_methods=frozenset(["GET", "POST"]),
            respect_retry_after_header=True,
            raise_on_status=False,
        )

        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    # ------------------------------------------------------------
    # Status check used by the sidebar
    # ------------------------------------------------------------
    def _probe(self, path: str, timeout=PING_TIMEOUT):
        """
        One quick GET without retries.
        Returns (http_status_code, error_name); one of them is None.
        """
        try:
            response = requests.get(
                f"{self.base_url}{path}",
                timeout=timeout,
            )
            return response.status_code, None

        except requests.Timeout:
            return None, "timeout"

        except requests.RequestException as exc:
            return None, type(exc).__name__

    def ping(self, timeout=PING_TIMEOUT) -> dict:
        """
        Never raises. Returns {"state": ..., "detail": ...} where state is:

          online    - /health answered OK (or the backend has no /health
                      route but the API root answers OK)
          degraded  - the API answers, but /health reports a problem
          waking    - no answer yet; a sleeping Render instance is
                      starting up (this can take up to a minute)
          offline   - the backend cannot be reached
        """

        health_code, health_error = self._probe("/health", timeout)

        if health_code is not None and health_code < 400:
            return {"state": "online", "detail": ""}

        if health_error == "timeout":
            # No answer at all: do not wait for a second timeout.
            return {
                "state": "waking",
                "detail": "No response yet from the backend.",
            }

        root_code, root_error = self._probe("/", timeout)
        root_ok = root_code is not None and root_code < 400

        if root_ok:
            if health_code == 404:
                # Older backend without a /health route: the API is up.
                return {"state": "online", "detail": ""}

            if health_code is not None:
                detail = f"/health returned HTTP {health_code}"
            else:
                detail = f"/health: {health_error}"

            return {"state": "degraded", "detail": detail}

        if root_error == "timeout" or root_code in (502, 503, 504):
            return {
                "state": "waking",
                "detail": "No response yet from the backend.",
            }

        if root_code is not None:
            detail = f"API root returned HTTP {root_code}"
        else:
            detail = f"Connection problem: {root_error}"

        return {"state": "offline", "detail": detail}

    def health_check(self):
        """Raises if the backend is unhealthy (kept for compatibility)."""
        response = self.session.get(
            f"{self.base_url}/health",
            timeout=DEFAULT_TIMEOUT,
        )

        if response.status_code == 404:
            response = self.session.get(
                f"{self.base_url}/",
                timeout=DEFAULT_TIMEOUT,
            )

        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------
    # Orders / predictions
    # ------------------------------------------------------------
    def get_order(self, order_id: str):
        """
        Look up an order by ID. Returns the order dict on success,
        or None if no order with that ID exists (HTTP 404).
        """
        response = self.session.get(
            f"{self.base_url}/orders/{quote(order_id.strip(), safe='')}",
            timeout=DEFAULT_TIMEOUT,
        )

        if response.status_code == 404:
            return None

        response.raise_for_status()
        data = response.json()
        return data.get("order", data)

    def predict(self, payload: dict):
        response = self.session.post(
            f"{self.base_url}/predict",
            json=payload,
            timeout=PREDICT_TIMEOUT,
        )

        if response.status_code >= 400:
            try:
                error_data = response.json()
            except Exception:
                error_data = {"detail": response.text}

            raise RuntimeError(
                error_data.get("detail")
                or error_data.get("error")
                or f"API request failed with HTTP {response.status_code}"
            )

        return response.json()

    def recent_predictions(self, limit: int = 10):
        response = self.session.get(
            f"{self.base_url}/predictions/recent",
            params={"limit": limit},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def get_info(self):
        response = self.session.get(
            f"{self.base_url}/info",
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
