import requests


class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def health_check(self):
        response = requests.get(
            f"{self.base_url}/health",
            timeout=15
        )

        response.raise_for_status()
        return response.json()

    def predict(self, payload: dict):
        response = requests.post(
            f"{self.base_url}/predict",
            json=payload,
            timeout=60
        )

        if response.status_code >= 400:
            try:
                error_data = response.json()
            except Exception:
                error_data = {
                    "detail": response.text
                }

            raise RuntimeError(
                error_data.get("detail")
                or error_data.get("error")
                or f"API request failed with HTTP {response.status_code}"
            )

        return response.json()

    def recent_predictions(self, limit: int = 10):
        response = requests.get(
            f"{self.base_url}/predictions/recent",
            params={"limit": limit},
            timeout=15
        )

        response.raise_for_status()
        return response.json()

    def get_info(self):
        response = requests.get(
            f"{self.base_url}/info",
            timeout=15
        )

        response.raise_for_status()
        return response.json()