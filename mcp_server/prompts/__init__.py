"""
MCP prompt templates registry.

To add a new prompt:
1. Create a file in this directory.
2. Define a `register(mcp)` function and decorate your prompts with `@mcp.prompt()`.
3. Import it below and call `register(mcp)` inside `register_all_prompts`.
"""

from mcp_server.prompts import daily_briefing


def register_all_prompts(mcp):
    daily_briefing.register(mcp)
