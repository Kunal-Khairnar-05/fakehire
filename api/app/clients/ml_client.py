"""HTTP client for the ml-service.

One shared httpx.Client per API process: it keeps connections to ml-service open
and reuses them (connection pooling), instead of a new TCP handshake per request.
"""
import time

import httpx

VERSION_REFRESH_SECONDS = 60


class MlServiceUnavailable(Exception):
    """ml-service is down, too slow, or returned an error."""


class MlClient:
    def __init__(self, base_url: str, timeout: float, internal_token: str | None = None):
        # timeout: if ml-service hangs, fail after N seconds instead of hanging the user too
        headers = {"X-Internal-Token": internal_token} if internal_token else {}
        self._http = httpx.Client(base_url=base_url, timeout=timeout, headers=headers)
        self._version: str | None = None
        self._version_checked_at = 0.0

    def predict(self, posting: dict) -> dict:
        try:
            response = self._http.post("/predict", json=posting)
            response.raise_for_status()          # 4xx/5xx -> exception
            return response.json()
        except httpx.HTTPError as exc:            # covers timeouts, refused connections, bad status
            raise MlServiceUnavailable(str(exc)) from exc

    def current_version(self) -> str:
        """Which model is ml-service running? Needed BEFORE calling it, because the model
        version is part of the cache key. Asked at most once a minute, remembered in between.
        If ml-service is down, the last known version is still returned, so cached verdicts
        keep being served during an outage."""
        if self._version and time.monotonic() - self._version_checked_at < VERSION_REFRESH_SECONDS:
            return self._version
        try:
            response = self._http.get("/health")
            response.raise_for_status()
            self._version = response.json()["model_version"]
            self._version_checked_at = time.monotonic()
        except httpx.HTTPError as exc:
            if self._version is None:             # never reached it at all
                raise MlServiceUnavailable(str(exc)) from exc
        return self._version

    def close(self) -> None:
        self._http.close()
