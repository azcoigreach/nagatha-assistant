"""WebSearchPlugin – provides internet search capability via SearXNG.

The plugin exposes two functions:

1. ``web_search`` – Run a query against the SearXNG instance and return the
   top results (title, url, snippet).
2. ``fetch_page`` – (internal) Fetch and return cleaned text from a URL.

The chat agent will typically:

* Call ``web_search`` first; decide which result(s) look promising.
* Optionally call ``fetch_page`` on individual links to get deeper context.

We limit the automatic depth to 2 links (configurable via arguments).
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List

import aiohttp
from bs4 import BeautifulSoup  # type: ignore

from nagatha_assistant.core.plugin import Plugin


logging = logging.getLogger(__name__)


SEARX_URL = "https://search.stranger.social"  # production instance


class WebSearchPlugin(Plugin):
    name = "web_search"
    version = "0.1.0"

    async def setup(self, config: Dict[str, Any]) -> None:  # noqa: D401
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20))

    async def teardown(self) -> None:  # noqa: D401
        if getattr(self, '_session', None):
            await self._session.close()

    # ------------------------------------------------------------------
    # Function specs – exposed to the LLM
    # ------------------------------------------------------------------

    def function_specs(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "web_search",
                "description": "Search the internet via SearXNG and return the top results.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "search phrase"},
                        "num_results": {
                            "type": "integer",
                            "description": "number of top results to return (default 3)",
                        },
                        "follow": {
                            "type": "boolean",
                            "description": "whether to fetch the result pages for summaries (default true)",
                        },
                    },
                    "required": ["query"],
                },
            }
            ,
            {
                "name": "fetch_page",
                "description": "Download the web page at the given URL and return a concise text summary.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "https://…"},
                        "max_chars": {
                            "type": "integer",
                            "description": "maximum characters in summary (default 500)",
                        },
                    },
                    "required": ["url"],
                },
            }
        ]

    # ------------------------------------------------------------------
    # Router
    # ------------------------------------------------------------------

    async def call(self, name: str, arguments: Dict[str, Any]) -> str:  # noqa: D401
        if name == "web_search":
            logging.debug("WebSearchPlugin called with name='%s' and arguments=%s", name, arguments)
            return await self._handle_search(arguments)
        if name == "fetch_page":
            logging.debug("WebSearchPlugin called with name='%s' and arguments=%s", name, arguments)
            return await self._handle_fetch(arguments)
        logging.error("WebSearchPlugin can only handle 'web_search' and 'fetch_page', not %s", name)
        raise ValueError(f"WebSearchPlugin cannot handle function {name}")

    # ------------------------------------------------------------------
    # Implementation helpers
    # ------------------------------------------------------------------

    async def _handle_search(self, args: Dict[str, Any]) -> str:
        query: str = args["query"]
        num_results: int = int(args.get("num_results", 3))
        follow: bool = bool(args.get("follow", True))

        logging.info("Search '%s' (num_results=%s, follow=%s)", query, num_results, follow)

        results = await self._search_searx(query, num_results)

        bullets: List[str] = []
        follow_tasks = []
        for idx, res in enumerate(results, 1):
            bullets.append(f"{idx}. {res['title']} – {res['url']}\n    {res['snippet']}")
            if follow:
                follow_tasks.append(self._fetch_and_summarise(res["url"]))

        extra_summaries: List[str] = []
        if follow_tasks:
            extra_summaries = await asyncio.gather(*follow_tasks, return_exceptions=False)

        bullet_text = "\n".join(bullets)
        if extra_summaries:
            bullet_text += "\n\nFollow-up summaries:\n" + "\n".join(extra_summaries)

        return bullet_text

    # ---------------------------- networking --------------------------------

    async def _search_searx(self, query: str, num: int) -> List[Dict[str, str]]:
        params = {"q": query, "format": "json", "language": "en", "safesearch": 1}
        async with self._session.get(f"{SEARX_URL}/search", params=params) as resp:
            data = await resp.json()

        results = []
        for entry in data.get("results", [])[:num]:
            results.append(
                {
                    "title": entry.get("title", ""),
                    "url": entry.get("url", ""),
                    "snippet": entry.get("content", "")[:300],
                }
            )
        return results

    async def _fetch_and_summarise(self, url: str) -> str:
        """Fetch page HTML and return a short text summary."""

        try:
            async with self._session.get(url, timeout=10) as resp:
                html = await resp.text(errors="ignore")
        except Exception as exc:  # noqa: BLE001
            logging.warning("Failed to fetch %s: %s", url, exc)
            return f"Could not fetch {url}"

        text = self._extract_text(html)
        summary = text[:500].replace("\n", " ")  # naive truncation
        return f"Summary from {url}: {summary}…"

    async def _handle_fetch(self, args: Dict[str, Any]) -> str:
        url: str = args["url"]
        max_chars: int = int(args.get("max_chars", 500))

        content = await self._fetch_and_summarise(url)
        # _fetch_and_summarise already truncates to 500, re-truncate if caller asked <500
        if len(content) > max_chars:
            content = content[: max_chars - 1] + "…"
        return content

    # -------------------------- util ----------------------------------------

    @staticmethod
    def _extract_text(html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        # Remove script/style
        for s in soup(["script", "style", "noscript"]):
            s.decompose()
        # get text
        text = soup.get_text(separator="\n")
        # collapse whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()
