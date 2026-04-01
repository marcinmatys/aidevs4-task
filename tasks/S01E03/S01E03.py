from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict

import requests
from dotenv import find_dotenv, load_dotenv

from tasks.base_task import BaseTask


class S01E03(BaseTask):
    """Register the proxy endpoint in the hub after confirming its readiness."""

    def __init__(self) -> None:
        _ = load_dotenv(find_dotenv())
        base_url = os.getenv("HUB_BASE_URL")
        super().__init__(base_url=base_url, task_name="proxy")
        self.proxy_base_url = os.getenv("PROXY_BASE_URL", "").rstrip("/")

    def run(self) -> Dict[str, Any]:
        """Validate proxy readiness and submit its public URL to the hub."""
        self._validate_configuration()
        endpoint_url = f"{self.proxy_base_url}/message"
        session_id = uuid.uuid4().hex

        self.logger.info("Waiting for proxy readiness at %s", endpoint_url)
        self._wait_for_proxy(endpoint_url)

        payload = {
            "url": endpoint_url,
            "sessionID": session_id,
        }
        self.logger.info("Submitting proxy registration payload: %s", payload)
        return self.verify(payload)

    def _validate_configuration(self) -> None:
        if not self.base_url:
            raise ValueError("Missing HUB_BASE_URL environment variable.")

        if not os.getenv("API_KEY", "").strip():
            raise ValueError("Missing API_KEY environment variable.")

        if not self.proxy_base_url:
            raise ValueError("Missing PROXY_BASE_URL environment variable.")

    def _wait_for_proxy(self, endpoint_url: str, timeout_seconds: int = 30, interval_seconds: float = 1.0) -> None:
        deadline = time.monotonic() + timeout_seconds
        last_error = "Unknown error"

        while time.monotonic() < deadline:
            try:
                response = requests.get(endpoint_url, timeout=5)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or "msg" not in payload:
                    raise ValueError("Proxy readiness response must be a JSON object with a 'msg' field.")
                self.logger.info("Proxy readiness confirmed: %s", payload)
                return
            except (requests.RequestException, ValueError) as error:
                last_error = str(error)
                self.logger.warning("Proxy not ready yet: %s", last_error)
                time.sleep(interval_seconds)

        raise ConnectionError(
            f"Proxy endpoint {endpoint_url} did not become ready within {timeout_seconds} seconds. Last error: {last_error}"
        )
