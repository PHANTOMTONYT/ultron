"""
MCP resources registry.

To add a new resource:
1. Create a file in this directory.
2. Define a `register(mcp)` function and decorate your resources with `@mcp.resource(uri)`.
3. Import it below and call `register(mcp)` inside `register_all_resources`.

No resources are registered yet - this is an empty skeleton.
"""


def register_all_resources(mcp):
    pass
