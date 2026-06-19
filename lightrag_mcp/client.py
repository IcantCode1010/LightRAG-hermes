from __future__ import annotations

from typing import Any

import httpx


class LightRAGClient:
    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        *,
        http: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._http = http

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key} if self.api_key else {}

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        close_client = self._http is None
        http = self._http or httpx.AsyncClient(timeout=60)
        try:
            response = await http.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers(),
                **kwargs,
            )
            response.raise_for_status()
            return response.json()
        finally:
            if close_client:
                await http.aclose()

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/health")

    async def pipeline_status(self) -> dict[str, Any]:
        return await self._request("GET", "/documents/pipeline_status")

    async def query(self, query: str, *, mode: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/query",
            json={"query": query, "mode": mode, "include_references": True},
        )

    async def insert_text(self, text: str) -> dict[str, Any]:
        return await self._request("POST", "/documents/text", json={"text": text})
