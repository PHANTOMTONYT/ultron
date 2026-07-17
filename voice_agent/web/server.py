"""
EDITH Voice Agent - Web Frontend
================================
Minimal standalone web page + LiveKit token server for talking to the
voice_agent/agent.py worker (run separately, in "dev" mode) over a real
browser tab instead of the terminal-only "console" mode or LiveKit's
hosted Agents Playground.

This is independent of the older backend/ app (different port, different
LiveKit room) so the two don't collide if both happen to be running.

Run:
  python voice_agent/web/server.py
Then open http://localhost:8090
"""

import os
import uuid
from pathlib import Path

from aiohttp import web
from dotenv import load_dotenv
from livekit import api

load_dotenv()

ROOM_NAME = "edith-voice-room"
WEB_DIR = Path(__file__).resolve().parent
PORT = int(os.getenv("VOICE_WEB_PORT", 8090))

LK_URL = os.getenv("LIVEKIT_URL", "").strip()
LK_API_KEY = os.getenv("LIVEKIT_API_KEY", "").strip()
LK_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "").strip()


async def handle_token(request):
    if not (LK_URL and LK_API_KEY and LK_API_SECRET):
        return web.json_response(
            {"error": "LiveKit credentials not configured on the server."}, status=500
        )

    identity = f"web-user-{uuid.uuid4().hex[:8]}"
    token = (
        api.AccessToken(LK_API_KEY, LK_API_SECRET)
        .with_identity(identity)
        .with_name("EDITH Web User")
        .with_grants(api.VideoGrants(room_join=True, room=ROOM_NAME))
        .to_jwt()
    )
    return web.json_response({"token": token, "url": LK_URL, "room": ROOM_NAME})


async def handle_index(request):
    return web.FileResponse(WEB_DIR / "index.html")


def main():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/token", handle_token)
    app.router.add_static("/", WEB_DIR, show_index=False)

    print(f"EDITH Voice Web: Serving on http://localhost:{PORT}")
    print(f"EDITH Voice Web: Room '{ROOM_NAME}' - make sure voice_agent/agent.py is running in 'dev' mode.")
    web.run_app(app, host="localhost", port=PORT, print=None)


if __name__ == "__main__":
    main()
