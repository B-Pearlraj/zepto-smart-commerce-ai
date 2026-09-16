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

    def list_orders(self, limit: int = 5):
        """
        Return a list of recent order IDs, for showing a few
        real example IDs in the chatbot UI.
        """
        response = requests.get(
            f"{self.base_url}/orders",
            params={"limit": limit},
            timeout=15
        )

        response.raise_for_status()
        return response.json().get("order_ids", [])

    def get_order(self, order_id: str):
        """
        Look up an order by ID. Returns the order dict on success,
        or None if no order with that ID exists (HTTP 404).
        """
        response = requests.get(
            f"{self.base_url}/orders/{order_id}",
            timeout=15
        )

        if response.status_code == 404:
            return None

        response.raise_for_status()
        return response.json()["order"]

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