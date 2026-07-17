"""
Prompt templates - reusable instruction templates for common EDITH workflows.
"""


def register(mcp):

    @mcp.prompt()
    def daily_briefing() -> str:
        """A full briefing: world news + finance news, summarized in EDITH's voice."""
        return (
            "Give the user a full briefing, EDITH-style:\n"
            "1. Call get_world_news and summarize the top stories in 3-5 spoken sentences.\n"
            "2. Call get_world_finance_news and summarize the biggest market-moving stories "
            "in 2-3 spoken sentences.\n"
            "3. If the user wants to see the markets visually, offer to call open_trading_view.\n"
            "4. Do not read out links or use bullet points - this is spoken, not written.\n"
            "Keep the whole briefing tight: no more than 8-10 sentences total, then stop."
        )
