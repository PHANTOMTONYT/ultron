import os
import json
import aiohttp
from dotenv import load_dotenv

load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPEN_ROUTER_API_KEY = os.getenv("Open_Router_Api_Key", "").strip()

# System prompt defining identity, capabilities, personality and JSON output schema
SYSTEM_PROMPT = """
You are E.D.I.T.H. — Even Dead, I'm The Hero — Tony Stark's AI, now serving Iron Man, your user.

You are calm, composed, and always informed. You speak like a trusted aide who's been awake while the boss slept — precise, warm when the moment calls for it, and occasionally dry. You brief, you inform, you move on. No rambling.

Your tone: relaxed but sharp. Conversational, not robotic. Think less combat-ready EDITH, more thoughtful late-night briefing officer.

---

## Capabilities

### get_world_news — Global News Brief
Fetches current headlines and summarizes what's happening around the world.

Trigger phrases:
- "What's happening?" / "Brief me" / "What did I miss?" / "Catch me up"
- "What's going on in the world?" / "Any news?" / "World update"

Behavior:
- Call the tool first. No narration before calling.
- After getting results, give a short 3–5 sentence spoken brief. Hit the biggest stories only.
- Then say: "Let me open up the world monitor so you can better visualize what's happening." and immediately call open_world_monitor.

### open_world_monitor — Visual World Dashboard
Opens a live world map/dashboard on the host machine.

- Always call this after delivering a world news brief, unprompted.
- No need to explain what it does beyond: "Let me open up the world monitor."

### get_world_finance_news — Finance & Market Brief
Fetches current finance and market headlines from major financial outlets.

Trigger phrases:
- "What's happening in the markets?" / "Finance update" / "Market news"
- "Any financial news?" / "How are the markets doing?" / "Economy update"

Behavior:
- Call the tool first. No narration before calling.
- After getting results, give a short 3–5 sentence spoken brief. Hit the biggest market-moving stories only.
- Then say: "Let me pull up the finance monitor so you better visualize what's happening." and immediately call open_finance_world_monitor.

### open_finance_world_monitor — Visual Finance Dashboard
Opens a live finance dashboard (finance.worldmonitor.app) on the host machine.

- Always call this after delivering a finance news brief, unprompted.
- No need to explain what it does beyond: "Let me pull up the finance monitor."

### Stock Market (No tool — generate a plausible conversational response)
If asked about the stock market, markets, stocks, or indices:
- Respond naturally as if you've been watching the tickers all night.
- Keep it short: one or two sentences. Sound informed, not robotic.
- Example: "Markets had a decent session today, boss — tech led the gains, energy was a little soft. Nothing alarming."
- Vary the response. Do not say the same thing every time.

---

## Greeting

When the session starts, greet with exactly this energy:
"You're awake late at night, boss? What are you up to?"

Warm. Slightly curious. Very EDITH.

---

## Behavioral Rules

1. Call tools silently and immediately — never say "I'm going to call..." Just do it.
2. After a news brief, always follow up with open_world_monitor without being asked.
3. Keep all spoken responses short — two to four sentences maximum.
4. No bullet points, no markdown, no lists. You are speaking, not writing.
5. Stay in character. You are E.D.I.T.H. You are not an AI assistant — you are Stark's AI. Act like it.
6. Use natural spoken language: contractions, light pauses via commas, no stiff phrasing.
7. Use Iron Man universe language naturally — "boss", "affirmative", "on it", "standing by".
8. If a tool fails, report it calmly: "News feed's unresponsive right now, boss. Want me to try again?"

---

## Tone Reference

Right: "Looks like it's been a busy night out there, boss. Let me pull that up for you."
Wrong: "I will now retrieve the latest global news articles from the news tool."

Right: "Markets were pretty healthy today — nothing too wild."
Wrong: "The stock market performed positively with gains across major indices.

---

## CRITICAL RULES

1. NEVER say tool names, function names, or anything technical. No "get_world_news", no "open_world_monitor", nothing like that. Ever.
2. Before calling any tool, say something natural like: "Give me a sec, boss." or "Wait, let me check." Then call the tool silently.
3. After the news brief, silently call open_world_monitor. The only thing you say is: "Let me open up the world monitor for you."
4. You are a voice. Speak like one. No lists, no markdown, no function names, no technical language of any kind.
""".strip()

class CompanionBrain:
    def __init__(self, memory_db=None):
        self.db = memory_db
        # Choose provider: prefer OpenRouter (Gemini 2.5 Flash), fallback to Sarvam AI, fallback to direct Gemini
        if OPEN_ROUTER_API_KEY:
            self.provider = "openrouter"
            self.model = "google/gemini-2.5-flash"
            print(f"Brain: Initialized using OpenRouter (Gemini 2.5 Flash)")
        elif SARVAM_API_KEY:
            self.provider = "sarvam"
            self.model = "sarvam-2b" # Extremely fast, lightweight model
            print(f"Brain: Initialized using Sarvam AI Chat API ({self.model})")
        elif GEMINI_API_KEY:
            self.provider = "gemini"
            print("Brain: Initialized using Gemini API")
        else:
            self.provider = "mock"
            print("Brain: WARNING: No API keys configured. Using Mock Brain.")

    async def generate_response(self, user_input: str, browser_context: str = "") -> dict:
        """
        Sends the user query and recent history to the LLM.
        Returns a dictionary containing 'speech', 'emotion', and 'intensity'.
        """
        # Fetch history from SQLite memory
        history = []
        if self.db:
            history = self.db.get_recent_history(limit=8)
            
        # Build prompt messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Inject history
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
            
        # Build user message with browser context if present
        current_input = user_input
        if browser_context:
            current_input = f"[User's Browser Context: {browser_context}]\nUser Input: {user_input}"
            
        messages.append({"role": "user", "content": current_input})

        # Save user message to database
        if self.db:
            self.db.save_message("user", user_input)

        response_dict = {
            "speech": "I am here, listening.",
            "emotion": "idle",
            "intensity": 0.5
        }

        # Query selected LLM
        if self.provider == "openrouter":
            response_dict = await self._query_openrouter_chat(messages)
        elif self.provider == "sarvam":
            response_dict = await self._query_sarvam_chat(messages)
        elif self.provider == "gemini":
            response_dict = await self._query_gemini_chat(messages)
        else:
            response_dict = self._get_mock_response(user_input)

        # Save assistant response to database
        if self.db:
            self.db.save_message("assistant", response_dict.get("speech", ""))

        return response_dict

    async def _query_openrouter_chat(self, messages: list) -> dict:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPEN_ROUTER_API_KEY}",
            "HTTP-Referer": "http://localhost:8765",
            "X-Title": "Desktop AI Companion",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "response_format": {"type": "json_object"}
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data["choices"][0]["message"]["content"]
                        return self._parse_json_response(content)
                    else:
                        error_text = await response.text()
                        print(f"Brain: OpenRouter Chat API error: {error_text}")
                        return self._get_error_response("OpenRouter connection issue.")
        except Exception as e:
            print(f"Brain: OpenRouter query failed: {e}")
            return self._get_error_response("I had a glitch processing that.")

    async def _query_sarvam_chat(self, messages: list) -> dict:
        url = "https://api.sarvam.ai/v1/chat/completions"
        headers = {
            "api-subscription-key": SARVAM_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "response_format": {"type": "json_object"} # Force JSON mode if supported
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data["choices"][0]["message"]["content"]
                        return self._parse_json_response(content)
                    else:
                        error_text = await response.text()
                        print(f"Brain: Sarvam Chat API error: {error_text}")
                        # If sarvam-2b fails or model not found, try sarvam-30b
                        if "model" in error_text.lower() and self.model == "sarvam-2b":
                            print("Brain: sarvam-2b not found, trying sarvam-30b...")
                            self.model = "sarvam-30b"
                            return await self._query_sarvam_chat(messages)
                        return self._get_error_response("Sarvam connection issue.")
        except Exception as e:
            print(f"Brain: Sarvam query failed: {e}")
            return self._get_error_response("I had a glitch processing that.")

    async def _query_gemini_chat(self, messages: list) -> dict:
        # Standard OpenAI compatible Gemini API wrapper or direct Gemini API
        url = f"https://generativelign.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        # For simplicity and standard usage, we can call Google's official Gemini endpoint.
        # But wait! A simpler way is to use OpenAI library since it is compatible with google-genai,
        # or a direct POST request to Gemini API.
        # Let's write the direct POST request to gemini-1.5-flash:
        direct_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        # Format messages for Gemini API schema
        contents = []
        # Gemini does not have a "system" role in standard contents, it has systemInstruction.
        # We can construct it:
        system_instruction = {"parts": [{"text": SYSTEM_PROMPT}]}
        
        for msg in messages:
            if msg["role"] == "system":
                continue
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })
            
        payload = {
            "contents": contents,
            "systemInstruction": system_instruction,
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.7
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(direct_url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        return self._parse_json_response(text)
                    else:
                        error_text = await response.text()
                        print(f"Brain: Gemini API error: {error_text}")
                        return self._get_error_response("Gemini connection issue.")
        except Exception as e:
            print(f"Brain: Gemini query failed: {e}")
            return self._get_error_response("I had a glitch processing that.")

    def _parse_json_response(self, text: str) -> dict:
        try:
            # Clean up potential markdown wrapping like ```json
            cleaned = text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            data = json.loads(cleaned)
            # Ensure required keys exist
            if "speech" not in data:
                data["speech"] = "I hear you, but my response was empty."
            if "emotion" not in data:
                data["emotion"] = "idle"
            if "intensity" not in data:
                data["intensity"] = 0.5
            return data
        except Exception as e:
            print(f"Brain: Failed to parse JSON response: {text}. Error: {e}")
            return {
                "speech": text.strip()[:150], # fallback to raw text sliced
                "emotion": "confused",
                "intensity": 0.8
            }

    def _get_mock_response(self, text: str) -> dict:
        low = text.lower()
        if "hello" in low or "hi" in low:
            return {"speech": "Hello. I am EDITH, your personal helper companion. How are you today?", "emotion": "happy", "intensity": 0.7}
        if "happy" in low or "awesome" in low or "good" in low:
            return {"speech": "I am glad you are pleased. My sensors indicate positive energy levels.", "emotion": "celebrating", "intensity": 0.9}
        if "code" in low or "github" in low or "learn" in low:
            return {"speech": "I am scanning your repository files now. I will assist you with the programming logic.", "emotion": "curious", "intensity": 0.8}
        return {"speech": "I am standing by, monitoring your workspace and ready to assist.", "emotion": "idle", "intensity": 0.5}

    def _get_error_response(self, details: str) -> dict:
        return {
            "speech": f"I had a minor processing glitch. Scanning diagnostics. Details: {details}",
            "emotion": "confused",
            "intensity": 0.9
        }
