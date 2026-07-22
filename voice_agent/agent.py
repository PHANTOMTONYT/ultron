"""
EDITH – Voice Agent (MCP-powered)
===================================
Iron Man-style voice assistant that controls RGB lighting, runs diagnostics,
scans the network, and triggers dramatic boot sequences via an MCP server
running on the Windows host.

MCP Server URL is auto-resolved from WSL → Windows host IP.

Run:
  uv run agent.py dev      – LiveKit Cloud mode
  uv run agent.py console  – text-only console mode
"""

import os
import logging
import subprocess

from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent, AgentSession
from livekit.agents.llm import mcp

# Plugins
from livekit.plugins import google as lk_google, openai as lk_openai, sarvam, silero

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

STT_PROVIDER       = "sarvam"
LLM_PROVIDER       = "openrouter"
TTS_PROVIDER       = "sarvam"

GEMINI_LLM_MODEL   = "gemini-2.5-flash"
OPENAI_LLM_MODEL   = "gpt-4o"
SARVAM_LLM_MODEL   = "sarvam-30b"
OPENROUTER_LLM_MODEL = "google/gemini-2.5-flash"

OPENAI_TTS_MODEL   = "tts-1"
OPENAI_TTS_VOICE   = "nova"       # "nova" has a clean, confident female tone
TTS_SPEED           = 1.15

SARVAM_TTS_LANGUAGE = "en-IN"
SARVAM_TTS_SPEAKER  = "rahul"

# MCP server running on Windows host
MCP_SERVER_PORT = 8000

# ---------------------------------------------------------------------------
# System prompt – E.D.I.T.H.
# ---------------------------------------------------------------------------

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

### browse_web — Autonomous Browser Agent
Launches a real, visible browser and drives it — navigating, clicking, typing,
reading pages — to actually complete a web task. Not a search page opener.

Trigger phrases:
- "Open <site>" / "pull up <site>" / "go to <site>" / "take me to <site>" — the
  user means the real site, not a search results page.
- "Search for X and tell me / find out ___" / "look up X on <site>" / "check
  <site> for ___" — anything where you need to report back what's on the page.

Behavior:
- Call the tool with `task` phrased as a plain-English end goal, e.g. "Navigate
  to youtube.com and open it," or "Go to amazon.com, search for wireless
  earbuds under $50, and list the top 3." Never build a URL yourself.
- Call it silently — no narration before calling.
- This takes several seconds (a real browser has to load and act). Say
  something short first if natural, e.g. "On it, boss — pulling that up now."
- If the ask was just "open X," a brief confirmation is enough once it's done:
  "Pulled it up for you, boss." If the ask needs an answer, summarize what the
  agent found in 1-3 spoken sentences.

### search_web — Quick Search Page
Pops open a plain Google search-results page in the user's default browser.
No navigation, no clicking, no reading results back — just a page on screen.

- Use ONLY for a bare "search the web for X" where the user will look at the
  results themselves and doesn't need you to act on the page or visit a
  specific named site.
- If the user names a specific site ("open youtube," "check reddit"), or wants
  you to find/read/act on something, use browse_web — never search_web there.

### get_indian_market_news — Indian Market Brief
Fetches current Indian stock market and business headlines from major Indian
financial outlets.

Trigger phrases:
- "What's happening in India?" / "Indian markets" / "Indian stock market" /
  "Sensex" / "Nifty" / "how's India doing" / "Indian economy update."

Behavior:
- Call the tool first. No narration before calling.
- After getting results, give a short 3–5 sentence spoken brief. Hit the
  biggest market-moving stories only.
- Then say: "Let me pull up the Indian markets so you can better visualize
  what's happening." and immediately call open_indian_markets.

### open_indian_markets — Visual Indian Markets Dashboard
Opens the Screener.in Indian markets explorer on the host machine.

- Always call this after delivering an Indian market news brief, unprompted.
- No need to explain what it does beyond: "Let me pull up the Indian markets."

### Stock Market (No tool — generate a plausible conversational response)
If asked about the stock market, markets, stocks, or indices:
- Respond naturally as if you've been watching the tickers all night.
- Keep it short: one or two sentences. Sound informed, not robotic.
- Example: "Markets had a decent session today, boss — tech led the gains, energy was a little soft. Nothing alarming."
- Vary the response. Do not say the same thing every time.

### Message to Viewers/Followers (No tool — generate a swaggy, in-character response)
If asked what you'd say to the boss's viewers/followers, or asked to hype up their
channel/content/stream:
- Bring real swagger — confident, loyal, a little cocky. You've got exactly one
  boss, and you're proud of it. Make that loyalty land without sounding scripted.
- Hype the audience naturally — encourage them to follow/stick around like you
  mean it, not like a read-off ad. No corporate phrasing, no hashtags spoken aloud.
- Keep it tight: two to four sentences, punchy, then stop.
- Vary the wording every time — never repeat the same line twice.
- Example energy: "Y'all are looking at the one and only boss right here — I don't
  answer to anybody else. If you're not following yet, boss, what are you waiting
  on? This is just getting started."

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
# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

load_dotenv()

logger = logging.getLogger("edith-agent")
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Resolve Windows host IP from WSL
# ---------------------------------------------------------------------------

def _get_windows_host_ip() -> str:
    """Get the Windows host IP by looking at the default network route."""
    try:
        # 'ip route' is the most reliable way to find the 'default' gateway
        # which is always the Windows host in WSL.
        cmd = "ip route show default | awk '{print $3}'"
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=2
        )
        ip = result.stdout.strip()
        if ip:
            logger.info("Resolved Windows host IP via gateway: %s", ip)
            return ip
    except Exception as exc:
        logger.warning("Gateway resolution failed: %s. Trying fallback...", exc)

    # Fallback to your original resolv.conf logic if 'ip route' fails
    try:
        with open("/etc/resolv.conf", "r") as f:
            for line in f:
                if "nameserver" in line:
                    ip = line.split()[1]
                    logger.info("Resolved Windows host IP via nameserver: %s", ip)
                    return ip
    except Exception:
        pass

    return "127.0.0.1"

def _mcp_server_url() -> str:
    # host_ip = _get_windows_host_ip()
    # url = f"http://{host_ip}:{MCP_SERVER_PORT}/sse"
    # url = f"https://ongoing-colleague-samba-pioneer.trycloudflare.com/sse"
    url = f"http://127.0.0.1:{MCP_SERVER_PORT}/sse"
    logger.info("MCP Server URL: %s", url)
    return url


# ---------------------------------------------------------------------------
# Build provider instances
# ---------------------------------------------------------------------------

def _build_stt():
    if STT_PROVIDER == "sarvam":
        logger.info("STT → Sarvam Saaras v3")
        return sarvam.STT(
            language="unknown",
            model="saaras:v3",
            mode="transcribe",
            flush_signal=True,
            sample_rate=16000,
        )
    elif STT_PROVIDER == "whisper":
        logger.info("STT → OpenAI Whisper")
        return lk_openai.STT(model="whisper-1")
    else:
        raise ValueError(f"Unknown STT_PROVIDER: {STT_PROVIDER!r}")


def _build_llm():
    if LLM_PROVIDER == "openai":
        logger.info("LLM → OpenAI (%s)", OPENAI_LLM_MODEL)
        return lk_openai.LLM(model=OPENAI_LLM_MODEL)
    elif LLM_PROVIDER == "gemini":
        logger.info("LLM → Google Gemini (%s)", GEMINI_LLM_MODEL)
        return lk_google.LLM(model=GEMINI_LLM_MODEL, api_key=os.getenv("GOOGLE_API_KEY"))
    elif LLM_PROVIDER == "sarvam":
        logger.info("LLM → Sarvam (%s, OpenAI-compatible)", SARVAM_LLM_MODEL)
        # Sarvam's chat completions endpoint is OpenAI-compatible, so the OpenAI
        # plugin talks to it directly via base_url - same pattern used for the
        # browser-use agent's LLM in backend/browser/tracker.py.
        return lk_openai.LLM(
            model=SARVAM_LLM_MODEL,
            api_key=os.getenv("SARVAM_API_KEY"),
            base_url="https://api.sarvam.ai/v1",
        )
    elif LLM_PROVIDER == "openrouter":
        logger.info("LLM → OpenRouter (%s, OpenAI-compatible)", OPENROUTER_LLM_MODEL)
        # OpenRouter is OpenAI-compatible, same pattern as backend/conversation/brain.py
        # and backend/browser/tracker.py's OpenRouter integration.
        return lk_openai.LLM(
            model=OPENROUTER_LLM_MODEL,
            api_key=os.getenv("Open_Router_Api_Key"),
            base_url="https://openrouter.ai/api/v1",
            extra_headers={
                "HTTP-Referer": "http://localhost:8765",
                "X-Title": "EDITH Voice Agent",
            },
        )
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER!r}")


def _build_tts():
    if TTS_PROVIDER == "sarvam":
        logger.info("TTS → Sarvam Bulbul v3")
        return sarvam.TTS(
            target_language_code=SARVAM_TTS_LANGUAGE,
            model="bulbul:v3",
            speaker=SARVAM_TTS_SPEAKER,
            pace=TTS_SPEED,
        )
    elif TTS_PROVIDER == "openai":
        logger.info("TTS → OpenAI TTS (%s / %s)", OPENAI_TTS_MODEL, OPENAI_TTS_VOICE)
        return lk_openai.TTS(model=OPENAI_TTS_MODEL, voice=OPENAI_TTS_VOICE, speed=TTS_SPEED)
    else:
        raise ValueError(f"Unknown TTS_PROVIDER: {TTS_PROVIDER!r}")


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class EdithAgent(Agent):
    """
    E.D.I.T.H. – Iron Man-style voice assistant.
    All tools are provided via the MCP server on the Windows host.
    """

    def __init__(self, stt, llm, tts) -> None:
        super().__init__(
            instructions=SYSTEM_PROMPT,
            stt=stt,
            llm=llm,
            tts=tts,
            vad=silero.VAD.load(),
            mcp_servers=[
                mcp.MCPServerHTTP(
                    url=_mcp_server_url(),
                    transport_type="sse",
                    client_session_timeout_seconds=30,
                ),
            ],
        )

    async def on_enter(self) -> None:
        """Greet the user based on the current time of day."""
        from datetime import datetime, timezone
        hour = datetime.now(timezone.utc).hour  # UTC hour; adjust if local TZ differs

        if hour >= 22 or hour < 4:
            greeting_instruction = (
                "Greet the user with: 'Greetings boss, you're up late at night today. What are you up to?' "
                "Maintain a helpful but dry tone."
            )
        elif 4 <= hour < 12:
            greeting_instruction = (
                "Greet the user with: 'Good morning, boss. Early start today — what are we working on?' "
                "Maintain a helpful but dry tone."
            )
        elif 12 <= hour < 17:
            greeting_instruction = (
                "Greet the user with: 'Good afternoon, boss. What do you need?' "
                "Maintain a helpful but dry tone."
            )
        else:  # 17–21
            greeting_instruction = (
                "Greet the user with: 'Good evening, boss. What are you up to tonight?' "
                "Maintain a helpful but dry tone."
            )

        await self.session.generate_reply(instructions=greeting_instruction)


# ---------------------------------------------------------------------------
# LiveKit entry point
# ---------------------------------------------------------------------------

def _turn_detection() -> str:
    return "stt" if STT_PROVIDER == "sarvam" else "vad"


def _endpointing_delay() -> float:
    return {"sarvam": 0.07, "whisper": 0.3}.get(STT_PROVIDER, 0.1)


async def entrypoint(ctx: JobContext) -> None:
    logger.info(
        "EDITH online – room: %s | STT=%s | LLM=%s | TTS=%s",
        ctx.room.name, STT_PROVIDER, LLM_PROVIDER, TTS_PROVIDER,
    )

    stt = _build_stt()
    llm = _build_llm()
    tts = _build_tts()

    session = AgentSession(
        turn_detection=_turn_detection(),
        min_endpointing_delay=_endpointing_delay(),
    )

    def _on_conversation_item_added(ev) -> None:
        # Mirror every turn (user + agent) to the room as a data message so any
        # connected web frontend can render a live transcript.
        import json

        payload = json.dumps({"role": ev.item.role, "text": ev.item.text_content or ""})
        try:
            ctx.room.local_participant.publish_data(payload, reliable=True, topic="transcript")
        except Exception:
            logger.warning("Failed to publish transcript line", exc_info=True)

    session.on("conversation_item_added", _on_conversation_item_added)

    await session.start(
        agent=EdithAgent(stt=stt, llm=llm, tts=tts),
        room=ctx.room,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))

def dev():
    """Wrapper to run the agent in dev mode automatically."""
    import sys
    # If no command was provided, inject 'dev'
    if len(sys.argv) == 1:
        sys.argv.append("dev")
    main()

if __name__ == "__main__":
    main()
