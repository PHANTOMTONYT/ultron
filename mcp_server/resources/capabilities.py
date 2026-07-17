"""
Self-describing resource: a live list of this server's registered tools, so
capabilities can be derived from the actual server instead of a hand-written
system prompt that can drift out of sync with what's really registered.
"""


def register(mcp):

    @mcp.resource("edith://capabilities")
    async def capabilities() -> str:
        """Lists every tool currently registered on this MCP server, with descriptions."""
        tools = await mcp.list_tools()
        lines = ["### EDITH - REGISTERED TOOLS (LIVE)\n"]
        for t in tools:
            lines.append(f"- **{t.name}**: {t.description or 'No description.'}")
        return "\n".join(lines)
