"""The single reusable Supermemory Local service.

All Supermemory HTTP access lives here — nothing else in the backend talks to :6767
directly. Built strictly against the VERIFIED local API (see docs/SUPERMEMORY_INTEGRATION.md).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.core.config import get_settings
from app.core.container import container_tags
from app.models.context_event import Memory

log = logging.getLogger("contextos.supermemory")


class SupermemoryError(RuntimeError):
    pass


class SupermemoryService:
    def __init__(self) -> None:
        s = get_settings()
        self.base_url = s.supermemory_base_url.rstrip("/")
        self._chunk_threshold = s.contextos_chunk_threshold
        headers = {"Content-Type": "application/json"}
        if s.supermemory_api_key:
            headers["Authorization"] = f"Bearer {s.supermemory_api_key}"
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(20.0, connect=5.0),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # ---- low level with a single bounded retry on transient network errors -------------
    async def _request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        last: Optional[Exception] = None
        for attempt in range(2):
            try:
                resp = await self._client.request(method, path, **kw)
                resp.raise_for_status()
                return resp
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                last = exc
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                    raise SupermemoryError(
                        f"{method} {path} -> {exc.response.status_code}: {exc.response.text[:300]}"
                    ) from exc
                log.warning("Supermemory %s %s failed (attempt %d): %s", method, path, attempt + 1, exc)
        raise SupermemoryError(f"{method} {path} failed: {last}")

    # ---- health -----------------------------------------------------------------------
    async def health(self) -> dict[str, Any]:
        """Report reachability for BOTH deployments:
        - Supermemory Local exposes GET /v3/health.
        - Supermemory Cloud may not, so fall back to a tiny authenticated list call.
        """
        # 1) local server health endpoint
        try:
            resp = await self._client.get("/v3/health", timeout=5.0)
            if resp.status_code == 200:
                body = resp.json()
                mode = "cloud" if "supermemory.ai" in self.base_url else "local"
                return {"reachable": True, "base_url": self.base_url,
                        "status": body.get("status", "ok"), "mode": mode}
        except Exception:  # noqa: BLE001
            pass
        # 2) fallback: a lightweight authenticated request (works on the hosted platform)
        try:
            resp = await self._client.post(
                "/v3/documents/list",
                json={"containerTags": container_tags(), "limit": 1},
                timeout=8.0,
            )
            if resp.status_code == 200:
                return {"reachable": True, "base_url": self.base_url, "status": "ok", "mode": "cloud"}
            return {"reachable": False, "base_url": self.base_url, "error": f"HTTP {resp.status_code}"}
        except Exception as exc:  # noqa: BLE001 - health must never raise
            return {"reachable": False, "base_url": self.base_url, "error": str(exc)}

    # ---- add memory -------------------------------------------------------------------
    async def add_memory(
        self,
        content: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
        custom_id: Optional[str] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "content": content,
            "containerTags": container_tags(),
            "metadata": metadata or {},
        }
        if custom_id:
            payload["customId"] = custom_id
        resp = await self._request("POST", "/v3/documents", json=payload)
        data = resp.json()
        return {"id": data.get("id"), "status": data.get("status")}

    # ---- semantic search --------------------------------------------------------------
    async def search(
        self,
        query: str,
        *,
        limit: int = 8,
        rerank: bool = True,
    ) -> list[Memory]:
        # Verified requirements: MUST pass containerTags, and a low chunkThreshold, or
        # valid semantic matches are dropped / an empty scope returns 0 results.
        payload = {
            "q": query,
            "containerTags": container_tags(),
            "limit": limit,
            "chunkThreshold": self._chunk_threshold,
            "rerank": rerank,
        }
        resp = await self._request("POST", "/v3/search", json=payload)
        data = resp.json()
        return [self._to_memory(r, from_search=True) for r in data.get("results", [])]

    # ---- list (timeline) --------------------------------------------------------------
    async def list_memories(
        self,
        *,
        limit: int = 100,
        page: int = 1,
        order: str = "desc",
    ) -> list[Memory]:
        payload = {
            "containerTags": container_tags(),
            "includeContent": True,
            "limit": limit,
            "page": page,
            "sort": "createdAt",
            "order": order,
        }
        resp = await self._request("POST", "/v3/documents/list", json=payload)
        data = resp.json()
        return [self._to_memory(m, from_search=False) for m in data.get("memories", [])]

    # ---- get one ----------------------------------------------------------------------
    async def get_memory(self, doc_id: str) -> Optional[Memory]:
        try:
            resp = await self._request("GET", f"/v3/documents/{doc_id}")
        except SupermemoryError:
            return None
        return self._to_memory(resp.json(), from_search=False)

    # ---- delete -----------------------------------------------------------------------
    async def delete_memory(self, doc_id: str) -> bool:
        resp = await self._request("DELETE", f"/v3/documents/{doc_id}")
        return resp.status_code in (200, 204)

    # ---- update (PATCH merges metadata; content edit re-embeds) ------------------------
    async def update_memory(
        self,
        doc_id: str,
        *,
        content: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        payload: dict[str, Any] = {}
        if content is not None:
            payload["content"] = content
        if metadata:
            payload["metadata"] = metadata
        if not payload:
            return True
        resp = await self._request("PATCH", f"/v3/documents/{doc_id}", json=payload)
        return resp.status_code in (200, 201)

    # ---- normalization ----------------------------------------------------------------
    @staticmethod
    def _to_memory(raw: dict[str, Any], *, from_search: bool) -> Memory:
        meta = raw.get("metadata") or {}
        # search results carry documentId; list/get carry id
        doc_id = raw.get("documentId") or raw.get("id") or ""
        content = raw.get("content")
        if content is None:
            chunks = raw.get("chunks") or []
            if chunks:
                content = " ".join(c.get("content", "") for c in chunks).strip()
        return Memory(
            id=str(doc_id),
            title=raw.get("title"),
            content=content,
            source_type=meta.get("source_type"),
            project_name=meta.get("project_name") or meta.get("project"),
            repository=meta.get("repository"),
            file_path=meta.get("file_path") or meta.get("file"),
            domain=meta.get("domain"),
            url=meta.get("url") or raw.get("url"),
            created_at=raw.get("createdAt"),
            metadata=meta,
            score=float(raw["score"]) if from_search and raw.get("score") is not None else None,
            pinned=bool(meta.get("contextos_pinned")),
            important=bool(meta.get("contextos_important")),
            irrelevant=bool(meta.get("contextos_irrelevant")),
            note=meta.get("contextos_note"),
            action=meta.get("action"),
        )


_service: Optional[SupermemoryService] = None


def get_supermemory() -> SupermemoryService:
    global _service
    if _service is None:
        _service = SupermemoryService()
    return _service
