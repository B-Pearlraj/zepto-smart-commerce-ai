from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

        # One shared session: reuses connections and retries
        # transient errors (rate limit / Render cold start).
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

    def health_check(self):
        """Try /health first; fall back to / if /health doesn't exist."""
        response = self.session.get(f"{self.base_url}/health", timeout=30)

        if response.status_code == 404:
            response = self.session.get(f"{self.base_url}/", timeout=30)

        response.raise_for_status()
        return response.json()

    def get_order(self, order_id: str):
        """
        Returns the order dict, or None if the order doesn't exist (404).
        """
        response = self.session.get(
            f"{self.base_url}/orders/{quote(order_id.strip(), safe='')}",
            timeout=30,
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
            timeout=60,
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
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_info(self):
        response = self.session.get(f"{self.base_url}/info", timeout=30)
        response.raise_for_status()
        return response.json()
