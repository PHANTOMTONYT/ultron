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

import mimetypes
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

load_dotenv()

ROOM_PREFIX = "edith-voice"
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

    # A fresh room name per connection - reusing one fixed room name means a
    # second connection reuses an already-created room, which never fires the
    # LiveKit "room created" event that automatic agent dispatch relies on, so
    # the worker never gets a job for it (registers fine, does nothing).
    room_name = f"{ROOM_PREFIX}-{uuid.uuid4().hex[:8]}"
    identity = f"web-user-{uuid.uuid4().hex[:8]}"
    token = (
        api.AccessToken(LK_API_KEY, LK_API_SECRET)
        .with_identity(identity)
        .with_name("EDITH Web User")
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )
    return web.json_response({"token": token, "url": LK_URL, "room": room_name})


async def handle_index(request):
    return web.FileResponse(WEB_DIR / "index.html")


def main():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/token", handle_token)
    app.router.add_static("/", WEB_DIR, show_index=False)

    print(f"EDITH Voice Web: Serving on http://localhost:{PORT}")
    print(f"EDITH Voice Web: Each connection gets a fresh '{ROOM_PREFIX}-*' room - make sure voice_agent/agent.py is running in 'dev' mode.")
    web.run_app(app, host="localhost", port=PORT, print=None)


if __name__ == "__main__":
    main()
