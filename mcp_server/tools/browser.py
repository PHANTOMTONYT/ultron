"""
Browser tools - autonomous, LLM-driven browsing (navigate, click, type, read pages)
via browser_use. Ported from backend/browser/tracker.py's BrowserTracker: same
persistent-Browser-singleton pattern (avoids the CDP target-attach race that happens
when a fresh Browser is spun up per task), just held as module state instead of on a
class, since mcp_server/tools has no owning instance.
"""

import os
import asyncio

from dotenv import load_dotenv

load_dotenv()

try:
    from browser_use import Agent, Browser, ChatOpenAI
    BROWSER_USE_AVAILABLE = True
except ImportError as e:
    BROWSER_USE_AVAILABLE = False
    print(f"browser.py: browser-use not available ({e}). browse_web will report unavailable.")

_browser = None  # persistent, keep_alive=True - mirrors BrowserTracker.__init__
_llm = None
_init_lock = asyncio.Lock()


def _build_llm():
    """Same provider-preference order as BrowserTracker: OpenRouter -> Sarvam -> Gemini."""
    open_router_key = os.getenv("Open_Router_Api_Key", "").strip()
    sarvam_key = os.getenv("SARVAM_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    if open_router_key:
        return ChatOpenAI(
            model="google/gemini-2.5-flash",
            api_key=open_router_key,
            base_url="https://openrouter.ai/api/v1",
        )
    if sarvam_key:
        return ChatOpenAI(
            model="sarvam-30b",
            api_key=sarvam_key,
            base_url="https://api.sarvam.ai/v1",
        )
    if gemini_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=gemini_key)
        except ImportError:
            return None
    return None


async def _get_browser_and_llm():
    global _browser, _llm
    if _browser is not None and _llm is not None:
        return _browser, _llm
    async with _init_lock:
        if _browser is None:
            _browser = Browser(
                headless=False,
                keep_alive=True,
                minimum_wait_page_load_time=0.5,
                wait_for_network_idle_page_load_time=1.0,
            )
        if _llm is None:
            _llm = _build_llm()
    return _browser, _llm


def register(mcp):

    @mcp.tool()
    async def browse_web(task: str) -> str:
        """
        Executes an autonomous, LLM-driven browsing task in a real, visible browser: it
        navigates to pages, clicks links/buttons, types into fields, and reads content -
        the same way a person would with a mouse and keyboard. This is the tool for
        anything that requires actually interacting with the web, including:

        - "Open <site>" / "pull up <site>" / "go to <site>" / "take me to <site>" - phrase
          the task as an instruction, e.g. "Navigate to youtube.com and open it."
        - "Search for X and tell me ___" / "find/look up/check X on <site>" - anything
          where you need to read the page and report back, not just show a search page.
        - Multi-step web workflows, e.g. "Go to amazon.com, search for wireless earbuds
          under $50, and list the top 3."

        Always pass `task` as a plain-English description of the END GOAL, not a URL -
        the agent decides which site to visit and what to click. Never construct or
        guess a URL yourself.

        Do not use this for a bare "search the web for X" where the user just wants a
        search-results page popped open with no further action or reading - use
        search_web for that instead.
        """
        if not BROWSER_USE_AVAILABLE:
            return "The browser agent isn't available on this machine, sir - browser-use failed to import."

        browser, llm = await _get_browser_and_llm()
        if llm is None:
            return "No LLM is configured for the browser agent, sir - set an OpenRouter, Sarvam, or Gemini API key."

        try:
            agent = Agent(task=task, llm=llm, browser=browser)
            history = await agent.run()
            result = history.final_result()
            return result or f"Done, sir - completed: {task}"
        except Exception as e:
            return f"The browser agent ran into a problem: {e}"
