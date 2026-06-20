from __future__ import annotations

from typing import Any
from pathlib import Path

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

    async def documents(self) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/documents/paginated",
            json={"page": 1, "page_size": 10},
        )

    async def query(self, query: str, *, mode: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/query",
            json={"query": query, "mode": mode, "include_references": True},
        )

    async def insert_text(
        self, text: str, *, file_source: str | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"text": text}
        if file_source is not None:
            payload["file_source"] = file_source
        return await self._request("POST", "/documents/text", json=payload)

    async def insert_file(
        self, path: Path, *, file_source: str | None = None
    ) -> dict[str, Any]:
        upload_name = file_source or path.name
        with path.open("rb") as handle:
            files = {"file": (upload_name, handle, "application/octet-stream")}
            return await self._request("POST", "/documents/upload", files=files)
