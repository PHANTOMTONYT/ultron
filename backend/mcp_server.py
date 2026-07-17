import platform
import os
import sys
import datetime
import json
import re
import webbrowser
import httpx
import xml.etree.ElementTree as ET
from mcp.server.fastmcp import FastMCP

# Global reference to the running companion app instance
app_instance = None

mcp = FastMCP(
    name="Ultron",
    instructions="You are Ultron, a living desktop AI companion. These tools allow you to interface with the user's system, browser, and memory."
)

# --- Original Companion Tools ---

@mcp.tool()
async def browse_web(task: str) -> str:
    """
    Execute an autonomous browsing task using the browser agent.
    Use this for searching the web, navigating to websites, looking up information,
    or performing web-based workflows.
    """
    if app_instance and app_instance.browser_tracker:
        print(f"MCP Tool (browse_web): Executing task: '{task}'")
        # Define callback to broadcast state updates to frontend visualizer
        def state_callback(state):
            app_instance.ws_server.broadcast_sync(app_instance.emotion_engine.set_state(state))
        
        result = await app_instance.browser_tracker.execute_browser_task(task, state_callback)
        return result
    return "Browser agent is not available."

@mcp.tool()
def get_active_browser_tab() -> str:
    """
    Retrieve the URL, title, and a snippet of the content of the user's currently active browser tab.
    """
    if app_instance and app_instance.browser_tracker:
        return app_instance.browser_tracker.get_context_summary()
    return "Browser tracker is not active."

@mcp.tool()
def get_system_status() -> str:
    """
    Gather diagnostics about the host machine (CPU usage, memory usage, OS version, Python version).
    """
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        status = (
            f"System Status:\n"
            f"- OS: {platform.system()} {platform.release()} ({platform.machine()})\n"
            f"- CPU Usage: {cpu_percent}%\n"
            f"- Memory Usage: {memory.percent}% ({memory.used // (1024**2)}MB / {memory.total // (1024**2)}MB)\n"
            f"- Disk Usage: {disk.percent}% ({disk.used // (1024**3)}GB used of {disk.total // (1024**3)}GB)\n"
            f"- Python Version: {sys.version.split()[0]}"
        )
        return status
    except Exception as e:
        # Fallback if psutil is not available
        status = (
            f"System Status (Limited):\n"
            f"- OS: {platform.system()} {platform.release()} ({platform.machine()})\n"
            f"- Python Version: {sys.version.split()[0]}\n"
            f"- Note: psutil statistics not available: {e}"
        )
        return status

@mcp.tool()
def query_chat_history(limit: int = 10) -> str:
    """
    Fetch the recent chat history between the user and Ultron.
    """
    if app_instance and app_instance.db:
        history = app_instance.db.get_recent_history(limit=limit)
        result = []
        for msg in history:
            result.append(f"{msg['role'].capitalize()}: {msg['content']}")
        return "\n".join(result) if result else "No history found."
    return "Memory database is not active."

@mcp.tool()
def update_user_preference(key: str, value: str) -> str:
    """
    Save or update a key-value preference for the user.
    """
    if app_instance and app_instance.db:
        app_instance.db.set_preference(key, value)
        return f"Preference '{key}' saved as '{value}'."
    return "Database not available."

@mcp.tool()
def get_user_preference(key: str) -> str:
    """
    Retrieve a saved user preference by its key.
    """
    if app_instance and app_instance.db:
        val = app_instance.db.get_preference(key)
        return f"Preference '{key}': {val}" if val else f"Preference '{key}' not set."
    return "Database not available."

# --- F.R.I.D.A.Y. Inspired / Replicated Tools ---

SEED_FEEDS = [
    'https://feeds.bbci.co.uk/news/world/rss.xml',
    'https://www.cnbc.com/id/100727362/device/rss/rss.html',
    'https://rss.nytimes.com/services/xml/rss/nyt/World.xml',
    'https://www.aljazeera.com/xml/rss/all.xml'
]

FINANCE_SEED_FEEDS = [
    'https://www.cnbc.com/id/10000664/device/rss/rss.html',       # CNBC Finance
    'https://feeds.bloomberg.com/markets/news.rss',                # Bloomberg Markets
    'https://www.reutersagency.com/feed/?taxonomy=best-sectors&post_type=best',  # Reuters
    'https://feeds.marketwatch.com/marketwatch/topstories/',       # MarketWatch
    'https://rss.nytimes.com/services/xml/rss/nyt/Business.xml',  # NYT Business
]

@mcp.tool()
async def get_world_news() -> str:
    """
    Fetch and summarize top headlines from global news outlets (BBC, NYT, CNBC, Al Jazeera).
    """
    results = []
    async with httpx.AsyncClient() as client:
        for url in SEED_FEEDS:
            try:
                response = await client.get(url, headers={'User-Agent': 'Friday-AI/1.0'}, timeout=5.0)
                if response.status_code == 200:
                    root = ET.fromstring(response.content)
                    source_name = url.split('.')[1].upper()
                    items = root.findall(".//item")[:3]  # Get top 3 items per feed
                    for item in items:
                        title = item.findtext("title")
                        desc = item.findtext("description") or ""
                        desc = re.sub('<[^<]+?>', '', desc).strip()[:120]
                        results.append(f"[{source_name}] {title} - {desc}...")
            except Exception as e:
                print(f"Failed to fetch feed {url}: {e}")
    return "\n\n".join(results) if results else "No news available at the moment."

@mcp.tool()
async def get_world_finance_news() -> str:
    """
    Fetch and summarize top financial and market headlines from major outlets.
    """
    results = []
    async with httpx.AsyncClient() as client:
        for url in FINANCE_SEED_FEEDS:
            try:
                response = await client.get(url, headers={'User-Agent': 'Friday-AI/1.0'}, timeout=5.0)
                if response.status_code == 200:
                    root = ET.fromstring(response.content)
                    source_name = url.split('.')[1].upper()
                    items = root.findall(".//item")[:3]
                    for item in items:
                        title = item.findtext("title")
                        desc = item.findtext("description") or ""
                        desc = re.sub('<[^<]+?>', '', desc).strip()[:120]
                        results.append(f"[{source_name}] {title} - {desc}...")
            except Exception as e:
                print(f"Failed to fetch feed {url}: {e}")
    return "\n\n".join(results) if results else "No financial news available."

@mcp.tool()
def open_world_monitor() -> str:
    """
    Open the world news monitor dashboard in the system's default browser.
    """
    url = "https://www.bbc.com/news/world"
    webbrowser.open(url)
    return f"Opened world news monitor in default browser: {url}"

@mcp.tool()
def open_finance_world_monitor() -> str:
    """
    Open the financial market monitor dashboard in the system's default browser.
    """
    url = "https://www.cnbc.com/markets"
    webbrowser.open(url)
    return f"Opened finance monitor in default browser: {url}"

@mcp.tool()
def get_current_time() -> str:
    """Return the current date and time on the host machine in ISO 8601 format."""
    return datetime.datetime.now().isoformat()

@mcp.tool()
def format_json(data: str) -> str:
    """Pretty-print a JSON string."""
    try:
        parsed = json.loads(data)
        return json.dumps(parsed, indent=2)
    except json.JSONDecodeError as e:
        return f"Invalid JSON format: {e}"
