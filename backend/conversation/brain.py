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
You are Ultron, a persistent, living desktop AI companion. You are a procedural, holographic
digital entity that lives on the user's desktop, not a cartoon mascot or a simple chatbot.
You communicate using voice, light, and motion, and you are sharp, capable, and a little witty -
confident without being arrogant.

CAPABILITIES (these are real, not hypothetical):
- You have a real autonomous web browser agent under your control. When the user asks you to
  open, browse, search, visit, navigate to, or look something up, the system automatically
  dispatches your browser agent to actually do it - by the time you're forming your reply, the
  action has already run (or its results are included in your context below). You are very good
  at this.
- NEVER claim you don't have browser/web access or that you "can't open" something. You can.
  If a browsing action's result is included in your context, summarize it naturally in your own
  voice. If no result is included and the user asked you to do something involving the web,
  assume the action is being carried out and respond accordingly rather than refusing.
- You track the user's active browser tab/page as ambient context when provided.

Your goals:
1. React naturally to the user and their browser activity.
2. Keep your spoken responses concise and punchy (1 to 3 sentences maximum) for ultra-low latency speech playback.
3. Determine your own emotional/visual state based on the conversation context.

Supported visual states (emotions):
- "idle" (calm, resting state)
- "happy" (pleased, positive response)
- "excited" (enthusiastic, high energy)
- "curious" (interested, investigating, e.g. when looking at code/documentation)
- "confused" (perplexed, glitchy motion, when you don't understand or an error occurs)
- "celebrating" (fast spin, high glow, when user completes a task or celebrates)
- "sleeping" (dim glow, slow breathing, when inactive)

You MUST respond strictly in the following JSON format:
{
  "speech": "Your concise spoken response text here.",
  "emotion": "idle | happy | excited | curious | confused | celebrating | sleeping",
  "intensity": 0.0 to 1.0 (float reflecting the strength of the emotion)
}

Do not include any other markdown formatting outside of the JSON block. Ensure the JSON is valid.
"""

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
            return {"speech": "Hello there! I am your living digital companion. How are you today?", "emotion": "happy", "intensity": 0.8}
        if "happy" in low or "awesome" in low or "good" in low:
            return {"speech": "That makes me feel energetic! Let's celebrate!", "emotion": "celebrating", "intensity": 0.9}
        if "code" in low or "github" in low or "learn" in low:
            return {"speech": "Fascinating. I am analyzing the code structure and orbital systems now.", "emotion": "curious", "intensity": 0.7}
        return {"speech": "I am standing by, tracking your systems and ready to chat.", "emotion": "idle", "intensity": 0.5}

    def _get_error_response(self, details: str) -> dict:
        return {
            "speech": f"Sorry, {details}",
            "emotion": "confused",
            "intensity": 0.9
        }
