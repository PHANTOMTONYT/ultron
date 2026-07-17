"""
Cached resource: exposes the most recently fetched news/finance briefing as
ambient, re-readable context without forcing a new live fetch.
"""

from mcp_server.state import get_cached


def register(mcp):

    @mcp.resource("edith://briefing/{topic}")
    def briefing(topic: str) -> str:
        """Returns the last successfully fetched briefing for `topic` ("world_news" or "finance_news")."""
        cached = get_cached(topic)
        if not cached:
            return f"No cached '{topic}' briefing yet this session - call the corresponding tool first."
        return f"(cached at {cached['fetched_at']})\n\n{cached['text']}"
