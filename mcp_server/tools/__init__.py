"""
MCP tools registry.

To add a new tool:
1. Create a file in this directory, e.g. `web.py`.
2. Define a `register(mcp)` function and decorate your tools with `@mcp.tool()`.
3. Import it below and call `register(mcp)` inside `register_all_tools`.
"""


from mcp_server.tools import web, browser

def register_all_tools(mcp):
    web.register(mcp)
    browser.register(mcp)
