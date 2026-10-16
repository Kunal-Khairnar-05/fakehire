"""HTTP client for the ml-service.

One shared httpx.Client per API process: it keeps connections to ml-service open
and reuses them (connection pooling), instead of a new TCP handshake per request.
"""
import httpx


class MlServiceUnavailable(Exception):
    """ml-service is down, too slow, or returned an error."""


class MlClient:
    def __init__(self, base_url: str, timeout: float):
        # timeout: if ml-service hangs, fail after N seconds instead of hanging the user too
        self._http = httpx.Client(base_url=base_url, timeout=timeout)

    def predict(self, posting: dict) -> dict:
        try:
            response = self._http.post("/predict", json=posting)
            response.raise_for_status()          # 4xx/5xx -> exception
            return response.json()
        except httpx.HTTPError as exc:            # covers timeouts, refused connections, bad status
            raise MlServiceUnavailable(str(exc)) from exc

    def close(self) -> None:
        self._http.close()
