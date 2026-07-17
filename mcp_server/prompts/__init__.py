"""
MCP prompt templates registry.

To add a new prompt:
1. Create a file in this directory.
2. Define a `register(mcp)` function and decorate your prompts with `@mcp.prompt()`.
3. Import it below and call `register(mcp)` inside `register_all_prompts`.

No prompts are registered yet - this is an empty skeleton.
"""


def register_all_prompts(mcp):
    pass
