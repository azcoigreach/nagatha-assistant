import asyncio

import pytest

from nagatha_assistant.core.plugin import PluginManager


@pytest.mark.asyncio
async def test_web_search_plugin(monkeypatch):
    """Verify that web_search function returns expected bullet list."""

    # Prepare fake results
    fake_results = [
        {"title": "Foo", "url": "https://example.com/foo", "snippet": "foo snippet"},
        {"title": "Bar", "url": "https://example.com/bar", "snippet": "bar snippet"},
        {"title": "Baz", "url": "https://example.com/baz", "snippet": "baz snippet"},
    ]

    async def fake_search(self, query, num):  # noqa: D401, ARG002
        return fake_results[:num]

    async def fake_summary(self, url):  # noqa: D401, ARG002
        return f"summary of {url}"

    # Discover plugins
    pm = PluginManager()
    await pm.discover()
    await pm.setup_all({})

    # Monkeypatch internal methods of WebSearchPlugin
    from nagatha_assistant.plugins.web_search import WebSearchPlugin

    monkeypatch.setattr(WebSearchPlugin, "_search_searx", fake_search)
    monkeypatch.setattr(WebSearchPlugin, "_fetch_and_summarise", fake_summary)

    # Call plugin function
    result = await pm.call_function(
        "web_search", {"query": "test", "num_results": 3, "follow": True}
    )

    # Should contain bullet points and summaries
    assert "1. Foo" in result
    assert "summary of https://example.com/foo" in result

    # Also test fetch_page directly
    page = await pm.call_function("fetch_page", {"url": "https://example.com/foo", "max_chars": 50})
    assert page.startswith("summary of https://example.com/foo")