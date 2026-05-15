"""Thin wrapper around Tavily search.

We avoid logging the API key. The tavily client itself shouldn't either, but
we keep wrappers explicit so future contributors don't accidentally print it.
"""

import asyncio
import logging
from typing import Any

from tavily import TavilyClient

from app.config import get_settings

log = logging.getLogger(__name__)


def _client() -> TavilyClient:
    settings = get_settings()
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY not configured")
    return TavilyClient(api_key=settings.tavily_api_key)


def _search_one(query: str, max_results: int = 8) -> dict[str, Any]:
    client = _client()
    return client.search(
        query=query,
        search_depth="advanced",
        max_results=max_results,
        include_answer=False,
        include_raw_content=False,
    )


async def search_many(queries: list[str], max_results: int = 8) -> list[dict[str, Any]]:
    """Run multiple queries concurrently. Each item: {'query': ..., 'results': [...]}"""

    async def one(q: str) -> dict[str, Any]:
        try:
            data = await asyncio.to_thread(_search_one, q, max_results)
            return {"query": q, "results": data.get("results", [])}
        except Exception as e:
            log.warning("tavily search failed for query=%r err=%s", q, e)
            return {"query": q, "results": [], "error": str(e)}

    return await asyncio.gather(*(one(q) for q in queries))


def dedupe_and_compact(batches: list[dict[str, Any]], per_result_chars: int = 600) -> list[dict]:
    """Flatten + dedupe by URL, truncate content."""
    seen: set[str] = set()
    out: list[dict] = []
    for batch in batches:
        for r in batch.get("results", []):
            url = r.get("url") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            content = (r.get("content") or "")[:per_result_chars]
            out.append(
                {
                    "url": url,
                    "title": r.get("title") or "",
                    "content": content,
                    "score": r.get("score"),
                    "query": batch["query"],
                }
            )
    return out
