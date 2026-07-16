import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPEN_ROUTER_API_KEY = os.getenv("Open_Router_Api_Key", "").strip()

# Attempt to import browser-use components
try:
    from browser_use import Agent, Browser, ChatOpenAI
    
    # Try importing optional langchain-google-genai
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        HAS_GEMINI_PLUGIN = True
    except ImportError:
        HAS_GEMINI_PLUGIN = False
        
    BROWSER_USE_AVAILABLE = True
except ImportError as e:
    BROWSER_USE_AVAILABLE = False
    print(f"Browser Tracker: Optional browser-use imports raised error: {e}. Browser agent will run in simulation mode.")

class BrowserTracker:
    def __init__(self):
        self.current_url = ""
        self.current_title = ""
        self.current_content = ""
        self.is_agent_running = False

        # Reuse a single Browser session across tasks instead of spawning a fresh
        # one each time. A fresh launch races the very first agent action against
        # the browser's CDP target still attaching, which manifests as repeated
        # "Cannot navigate - browser not connected" / "Target ... not found" errors
        # and burns several retry steps before recovering (browser-use/browser-use
        # CDP target-attach race, still present as of browser-use 0.13.4).
        self.browser = None
        if BROWSER_USE_AVAILABLE:
            self.browser = Browser(
                headless=False,
                keep_alive=True,
                minimum_wait_page_load_time=0.5,
                wait_for_network_idle_page_load_time=1.0,
            )

        # Configure LLM for browser-use agent
        self.llm = None
        if BROWSER_USE_AVAILABLE:
            if OPEN_ROUTER_API_KEY:
                # OpenRouter is OpenAI-compatible (using browser_use wrapper)
                self.llm = ChatOpenAI(
                    model="google/gemini-2.5-flash",
                    api_key=OPEN_ROUTER_API_KEY,
                    base_url="https://openrouter.ai/api/v1"
                )
                print("Browser Tracker: Configured OpenRouter (Gemini 2.5 Flash) for browser-use agent.")
            elif SARVAM_API_KEY:
                # Sarvam AI is OpenAI-compatible (using browser_use wrapper)
                self.llm = ChatOpenAI(
                    model="sarvam-30b",
                    api_key=SARVAM_API_KEY,
                    base_url="https://api.sarvam.ai/v1"
                )
                print("Browser Tracker: Configured ChatOpenAI (Sarvam-30b) for browser-use agent.")
            elif GEMINI_API_KEY and HAS_GEMINI_PLUGIN:
                self.llm = ChatGoogleGenerativeAI(
                    model="gemini-1.5-flash",
                    google_api_key=GEMINI_API_KEY
                )
                print("Browser Tracker: Configured ChatGoogleGenerativeAI (Gemini) for browser-use agent.")

    def update_context(self, url: str, title: str, content: str = ""):
        """
        Updates the active page context tracking.
        """
        self.current_url = url
        self.current_title = title
        self.current_content = content
        print(f"Browser: Focus changed - Title: '{title}', URL: '{url}'")

    def get_context_summary(self) -> str:
        if not self.current_url:
            return ""
        return f"Active Tab: {self.current_title} ({self.current_url}). Content snippet: {self.current_content[:200]}"

    def determine_reaction(self, url: str) -> dict:
        """
        Examines URL and returns a visual state override if matched.
        """
        low_url = url.lower()
        if "youtube.com" in low_url or "youtu.be" in low_url:
            return {"emotion": "excited", "intensity": 0.8}
        elif "github.com" in low_url:
            return {"emotion": "curious", "intensity": 0.9}
        elif "stackoverflow.com" in low_url or "docs." in low_url or "wiki" in low_url:
            return {"emotion": "thinking", "intensity": 0.6}
        elif "amazon.com" in low_url or "shopping" in low_url or "ebay" in low_url:
            return {"emotion": "happy", "intensity": 0.7}
        return {}

    async def execute_browser_task(self, task_description: str, event_callback=None) -> str:
        """
        Runs an autonomous browsing task using browser-use.
        Calls event_callback(state) to notify backend about state changes.
        """
        if not BROWSER_USE_AVAILABLE or not self.llm:
            print("Browser: browser-use not available. Simulating task...")
            if event_callback:
                event_callback("thinking")
            await asyncio.sleep(3.0)
            return f"[Simulated Browser result for task: '{task_description}'] Found matching details. Standard results loaded successfully."
            
        self.is_agent_running = True
        if event_callback:
            event_callback("thinking")
            
        try:
            print(f"Browser: Starting browser-use agent for task: '{task_description}'")

            # Initialize agent against the persistent, already-warmed-up browser session
            agent = Agent(
                task=task_description,
                llm=self.llm,
                browser=self.browser
            )
            
            # Run the task
            history = await agent.run()
            result = history.final_result()
            print(f"Browser: Task completed successfully. Result: {result}")
            return result
        except Exception as e:
            print(f"Browser: Agent task failed: {e}")
            return f"Failed to complete the browser task due to an error: {e}"
        finally:
            self.is_agent_running = False
            if event_callback:
                event_callback("idle")
