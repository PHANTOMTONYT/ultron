import asyncio
import os
import re
import base64
from pathlib import Path
from dotenv import load_dotenv

from backend.memory.db import MemoryDB
from backend.conversation.brain import CompanionBrain
from backend.browser.tracker import BrowserTracker
from backend.emotion.engine import EmotionEngine
from backend.websocket.server import WebSocketServer
from backend.speech.tts import synthesize_speech
from backend.speech.stt import pcm_to_wav, transcribe_audio_bytes

# Try importing livekit components
try:
    from livekit import api, rtc
    import numpy as np
    LIVEKIT_AVAILABLE = True
except ImportError:
    LIVEKIT_AVAILABLE = False
    print("Backend App: LiveKit python package is not installed or numpy is missing. Running without LiveKit WebRTC channel.")

load_dotenv()

class DesktopCompanionApp:
    def __init__(self):
        print("Starting Living Desktop AI Companion backend...")
        
        # 1. Initialize subsystems
        self.db = MemoryDB()
        self.brain = CompanionBrain(memory_db=self.db)
        self.browser_tracker = BrowserTracker()
        self.emotion_engine = EmotionEngine()
        frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
        self.ws_server = WebSocketServer(
            host=os.getenv("WS_HOST", "localhost"),
            port=int(os.getenv("WS_PORT", 8765)),
            static_dir=str(frontend_dir)
        )
        
        # LiveKit configuration
        self.lk_url = os.getenv("LIVEKIT_URL", "").strip()
        self.lk_api_key = os.getenv("LIVEKIT_API_KEY", "").strip()
        self.lk_api_secret = os.getenv("LIVEKIT_API_SECRET", "").strip()
        self.lk_room_name = "living-companion-room"
        
        self.lk_room = None
        self.lk_audio_source = None
        self.lk_track = None
        self.use_livekit = LIVEKIT_AVAILABLE and bool(self.lk_url and self.lk_api_key and self.lk_api_secret)
        
        if self.use_livekit:
            print(f"LiveKit: Configured to connect to {self.lk_url} in room '{self.lk_room_name}'")
        else:
            print("LiveKit: Credentials not set or LiveKit library not available. Falling back to WebSocket client-side audio loop.")
            
        # Lock for conversational pipeline to avoid overlapping outputs
        self.pipeline_lock = asyncio.Lock()

        # True while agent TTS audio is actively being played over LiveKit, so the
        # mic VAD can ignore speaker bleed instead of self-triggering a new turn.
        self.agent_speaking = False
        
        # 2. Register WebSocket Event Handlers
        self.ws_server.register_callback("user_input", self.handle_user_input)
        self.ws_server.register_callback("listening_started", self.handle_listening_started)
        self.ws_server.register_callback("listening_stopped", self.handle_listening_stopped)
        self.ws_server.register_callback("speech_started", self.handle_speech_started)
        self.ws_server.register_callback("speech_finished", self.handle_speech_finished)
        self.ws_server.register_callback("state_request", self.handle_state_request)
        self.ws_server.register_callback("browser_update", self.handle_browser_update)
        self.ws_server.register_callback("request_livekit_token", self.handle_token_request)
        self.ws_server.register_callback("toggle_voice_mode", self.handle_toggle_voice_mode)


    async def start(self):
        # Start WebSocket Server
        await self.ws_server.start()
        
        # Start LiveKit client agent connection if credentials configured
        if self.use_livekit:
            asyncio.create_task(self.connect_to_livekit())
            
        # Broadcast initial idle state
        await self.ws_server.broadcast(self.emotion_engine.set_state("idle"))
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            await self.ws_server.stop()
            if self.lk_room:
                await self.lk_room.disconnect()

    async def connect_to_livekit(self):
        """
        Connects backend Python client to the LiveKit Room as the Agent entity.
        """
        try:
            self.lk_room = rtc.Room()
            
            # Generate agent access token
            agent_token = api.AccessToken(self.lk_api_key, self.lk_api_secret) \
                .with_identity("companion-agent") \
                .with_name("AI Companion Agent") \
                .with_grants(api.VideoGrants(room_join=True, room=self.lk_room_name)) \
                .to_jwt()
                
            # Handle remote user tracks (VAD voice listener)
            @self.lk_room.on("track_subscribed")
            def on_track_subscribed(track, publication, participant):
                if track.kind == rtc.TrackKind.KIND_AUDIO:
                    print(f"LiveKit: Subscribed to user track {track.sid} from participant {participant.identity}")
                    audio_stream = rtc.AudioStream(track, sample_rate=16000, num_channels=1)
                    asyncio.create_task(self.process_livekit_audio_stream(audio_stream))
            
            print("LiveKit: Connecting to room...")
            await self.lk_room.connect(self.lk_url, agent_token)
            print("LiveKit: Connected successfully!")
            
            # Initialize AudioSource for streaming synthesized WAV -> PCM audio
            self.lk_audio_source = rtc.AudioSource(16000, 1) # 16kHz sample rate, mono
            self.lk_track = rtc.LocalAudioTrack.create_audio_track("agent-voice", self.lk_audio_source)
            
            # Publish backend track
            options = rtc.TrackPublishOptions()
            options.source = rtc.TrackSource.SOURCE_MICROPHONE
            await self.lk_room.local_participant.publish_track(self.lk_track, options)
            print("LiveKit: Published local audio track to room.")
            
        except Exception as e:
            print(f"LiveKit: Connection failed: {e}. Falling back to default WebSockets.")
            self.use_livekit = False

    async def process_livekit_audio_stream(self, audio_stream):
        """
        Subscribes to user mic frames, computes energy thresholds (VAD), 
        accumulates PCM buffer, and calls transcribers on silence.
        """
        accumulated_pcm = bytearray()
        speaking = False
        silence_frames = 0
        max_silence_frames = 60 # 60 frames * 20ms = 1.2 seconds of silence to trigger response
        
        try:
            async for frame_event in audio_stream:
                # Ignore mic input entirely while the agent itself is speaking, so
                # speaker bleed picked up by the mic (no echo cancellation) can't
                # self-trigger a new "user utterance" mid-response.
                if self.agent_speaking:
                    if speaking:
                        speaking = False
                        accumulated_pcm = bytearray()
                        silence_frames = 0
                    continue

                frame = frame_event.frame
                samples = np.frombuffer(frame.data, dtype=np.int16)
                if len(samples) == 0:
                    continue

                # Compute RMS energy amplitude of the 16-bit PCM block
                rms = np.sqrt(np.mean(samples.astype(np.float32)**2))
                
                # Simple energy threshold VAD
                if rms > 600: # Threshold above noise floor
                    if not speaking:
                        speaking = True
                        print("LiveKit VAD: User started speaking...")
                        # Tell visualizer to go to listening purple
                        await self.ws_server.broadcast(self.emotion_engine.set_state("listening", 0.8))
                        
                    accumulated_pcm.extend(frame.data)
                    silence_frames = 0
                else:
                    if speaking:
                        accumulated_pcm.extend(frame.data)
                        silence_frames += 1
                        
                        if silence_frames >= max_silence_frames:
                            speaking = False
                            print(f"LiveKit VAD: User stopped speaking. Processing {len(accumulated_pcm)} PCM bytes.")
                            await self.ws_server.broadcast(self.emotion_engine.set_state("thinking", 0.8))
                            
                            # Fire off processing task asynchronously so stream loop isn't blocked
                            pcm_payload = bytes(accumulated_pcm)
                            asyncio.create_task(self.handle_voice_utterance(pcm_payload))
                            accumulated_pcm = bytearray()
                            silence_frames = 0
        except Exception as e:
            print(f"LiveKit VAD: Error parsing audio track: {e}")

    async def handle_voice_utterance(self, pcm_data: bytes):
        """
        Helper task to convert voice track to WAV, run Sarvam STT, and reply.
        """
        try:
            # Convert raw 16kHz mono PCM to WAV buffer
            wav_bytes = pcm_to_wav(pcm_data, sample_rate=16000, num_channels=1)
            
            # Request transcription from Sarvam
            user_text = await transcribe_audio_bytes(wav_bytes, language_code="en-IN")
            user_text = user_text.strip()
            
            if not user_text:
                print("LiveKit VAD: Transcribed text empty, ignoring.")
                await self.ws_server.broadcast(self.emotion_engine.set_state("idle", 0.5))
                return
                
            print(f"LiveKit VAD: Transcribed user speech: '{user_text}'")
            
            # Broadcast the transcript subtitle to client
            await self.ws_server.broadcast({
                "type": "captions_overlay", 
                "text": user_text, 
                "active": True
            })
            
            # Forward transcript to core response handler
            await self.handle_user_input({"text": user_text})
            
        except Exception as e:
            print(f"LiveKit VAD: Utterance callback failed: {e}")
            await self.ws_server.broadcast(self.emotion_engine.set_state("idle", 0.5))

    async def handle_token_request(self, data):
        """
        Generates and returns room join tokens for the Electron client.
        """
        if not self.use_livekit:
            await self.ws_server.broadcast({"type": "livekit_unsupported"})
            return
            
        try:
            token = api.AccessToken(self.lk_api_key, self.lk_api_secret) \
                .with_identity("desktop-user") \
                .with_name("Desktop Companion User") \
                .with_grants(api.VideoGrants(room_join=True, room=self.lk_room_name)) \
                .to_jwt()
                
            await self.ws_server.broadcast({
                "type": "livekit_token",
                "token": token,
                "url": self.lk_url
            })
        except Exception as e:
            print(f"LiveKit: Token generation failed: {e}")

    async def handle_toggle_voice_mode(self, data):
        """
        Switches between LiveKit WebRTC and standard failsafe TCP WebSockets.
        """
        mode = data.get("mode", "ws")
        print(f"App: Voice channel mode switch requested -> {mode}")
        if mode == "ws":
            self.use_livekit = False
            if self.lk_room:
                try:
                    await self.lk_room.disconnect()
                    print("LiveKit: Agent disconnected from room for fallback mode.")
                except Exception as e:
                    print(f"LiveKit: Disconnection error: {e}")
                self.lk_room = None
        else:
            if LIVEKIT_AVAILABLE and bool(self.lk_url and self.lk_api_key and self.lk_api_secret):
                self.use_livekit = True
                if not self.lk_room:
                    asyncio.create_task(self.connect_to_livekit())
                print("LiveKit: Agent activating WebRTC...")
            else:
                self.use_livekit = False
                await self.ws_server.broadcast({"type": "livekit_unsupported"})
                print("LiveKit: Cannot activate. Missing packages or credentials.")

    # --- Event Handler Callbacks ---

    async def handle_listening_started(self, data):
        response_event = self.emotion_engine.process_event("listening_started")
        await self.ws_server.broadcast(response_event)

    async def handle_listening_stopped(self, data):
        response_event = self.emotion_engine.process_event("listening_stopped")
        await self.ws_server.broadcast(response_event)

    async def handle_speech_started(self, data):
        response_event = self.emotion_engine.process_event("speech_started")
        await self.ws_server.broadcast(response_event)

    async def handle_speech_finished(self, data):
        response_event = self.emotion_engine.process_event("speech_finished")
        await self.ws_server.broadcast(response_event)

    async def handle_state_request(self, data):
        target_state = data.get("state", "idle")
        intensity = data.get("intensity", 0.5)
        response_event = self.emotion_engine.set_state(target_state, intensity)
        await self.ws_server.broadcast(response_event)

    async def handle_browser_update(self, data):
        url = data.get("url", "")
        title = data.get("title", "")
        content = data.get("content", "")
        
        # Update browser tracking context
        self.browser_tracker.update_context(url, title, content)
        
        # Process visual state reaction based on URL
        response_event = self.emotion_engine.process_event("browser_changed", {"url": url})
        if response_event:
            await self.ws_server.broadcast(response_event)

    async def handle_user_input(self, data):
        """
        Process transcribed voice speech or typed messages from user.
        """
        async with self.pipeline_lock:
            user_text = data.get("text", "").strip()
            if not user_text:
                return

            print(f"App: Processing input -> '{user_text}'")
            
            # Immediately notify frontend of thinking mode
            await self.ws_server.broadcast(self.emotion_engine.set_state("thinking", 0.8))
            
            # Stop any playing audio on the frontend before responding
            await self.ws_server.broadcast({"type": "clear_audio"})

            # Check if this is a web navigation/browsing task
            keywords = ["browse", "search", "look up", "navigate to", "google", "website", "web page", "pull up", "visit"]
            has_keyword = any(word in user_text.lower() for word in keywords)

            # Any "open <something>" command is a browse request - the assistant has no other
            # concept of "opening" things, so there's no need to guess whether the target looks
            # like a URL/known site first (that guess was excluding things like "open netflix").
            starts_with_open = bool(re.match(r"^(please\s+)?(can you\s+)?open\s+\S", user_text.lower()))

            is_browse_task = has_keyword or starts_with_open or user_text.startswith("/browse")
            
            if is_browse_task:
                # Run Browser Use agent!
                task = user_text.replace("/browse", "").strip()
                await self.ws_server.broadcast({"type": "captions_overlay", "text": f"Launching browser to: {task}", "active": True})
                
                # Run browser use task (non-blocking)
                browser_result = await self.browser_tracker.execute_browser_task(
                    task, 
                    lambda state: self.ws_server.broadcast_sync(self.emotion_engine.set_state(state))
                )
                
                # Ask LLM brain to summarize findings and answer
                browser_prompt = f"The user asked to browse: '{task}'. Here are the findings from the web browser agent: {browser_result}\nSummarize and answer the user."
                response = await self.brain.generate_response(browser_prompt, self.browser_tracker.get_context_summary())
            else:
                # Standard LLM conversation with browser context injected
                browser_context = self.browser_tracker.get_context_summary()
                response = await self.brain.generate_response(user_text, browser_context)

            # Broadcast generated emotion change immediately (before speech starts)
            emotion = response.get("emotion", "idle")
            intensity = response.get("intensity", 0.5)
            await self.ws_server.broadcast(self.emotion_engine.set_emotion(emotion, intensity))

            speech_text = response.get("speech", "")
            print(f"App: Brain output speech -> '{speech_text}'")
            
            # Direct audio playing: LiveKit WebRTC vs direct WebSockets fallback
            if self.use_livekit and self.lk_audio_source:
                # Route audio over LiveKit. Awaited (not create_task) so the pipeline
                # lock stays held until playback fully finishes - otherwise a
                # self-triggered VAD utterance could start a second playback task
                # that writes frames to the same audio source concurrently.
                await self.play_speech_over_livekit(speech_text)
            else:
                # Route audio over WebSockets (standard audio handler)
                await self.stream_speech_over_websockets(speech_text)

    async def play_speech_over_livekit(self, speech_text: str):
        """
        Synthesize speech sentences in WAV format, strip headers, and stream 16-bit PCM over LiveKit WebRTC.
        """
        # Split sentences
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', speech_text) if s.strip()]
        if not sentences:
            sentences = [speech_text]

        await self.ws_server.broadcast(self.emotion_engine.set_state("speaking", 0.8))
        self.agent_speaking = True

        for sentence in sentences:
            try:
                # Broadcast the subtitles for this active sentence
                await self.ws_server.broadcast({
                    "type": "captions_overlay", 
                    "text": sentence, 
                    "active": True
                })
                
                # Fetch WAV audio from Sarvam
                lang = "en-IN"
                if any(ord(char) > 127 for char in sentence):
                    lang = "hi-IN"
                
                print(f"LiveKit Audio: Synthesizing sentence: '{sentence}'")
                audio_b64 = await synthesize_speech(sentence, lang, speech_format="wav")
                audio_bytes = base64.b64decode(audio_b64)
                
                # RIFF WAV header is 44 bytes. Remaining bytes are 16kHz mono PCM.
                pcm_data = audio_bytes[44:]
                
                # Stream frames: 16000Hz * 0.02s * 2 bytes = 640 bytes per 20ms frame
                chunk_size = 640
                for i in range(0, len(pcm_data), chunk_size):
                    chunk = pcm_data[i:i+chunk_size]
                    if len(chunk) < chunk_size:
                        # Pad last frame
                        chunk = chunk + b'\x00' * (chunk_size - len(chunk))
                        
                    frame = rtc.AudioFrame(
                        data=chunk,
                        sample_rate=16000,
                        num_channels=1,
                        samples_per_channel=320 # 16000 * 0.02
                    )
                    
                    await self.lk_audio_source.capture_frame(frame)
                    await asyncio.sleep(0.02) # Pace the frames
                    
            except Exception as e:
                print(f"LiveKit: Error in TTS stream: {e}")

        self.agent_speaking = False
        # Fade out overlay and go idle
        await self.ws_server.broadcast({"type": "captions_overlay", "active": False})
        await self.ws_server.broadcast(self.emotion_engine.set_state("idle", 0.5))

    async def stream_speech_over_websockets(self, speech_text: str):
        """
        Failsafe fallback: synthesizes as MP3 and pushes base64 files over WS to client player.
        """
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', speech_text) if s.strip()]
        if not sentences:
            sentences = [speech_text]
            
        for sentence in sentences:
            try:
                lang = "en-IN"
                if any(ord(char) > 127 for char in sentence):
                    lang = "hi-IN"
                    
                audio_b64 = await synthesize_speech(sentence, lang, speech_format="mp3")
                
                await self.ws_server.broadcast({
                    "type": "audio_chunk",
                    "audio": audio_b64,
                    "text": sentence
                })
            except Exception as e:
                print(f"WebSockets Fallback: Speech generation failed for sentence '{sentence}': {e}")
                await self.ws_server.broadcast({
                    "type": "audio_chunk",
                    "audio": "",
                    "text": sentence
                })

if __name__ == "__main__":
    app = DesktopCompanionApp()
    try:
        asyncio.run(app.start())
    except KeyboardInterrupt:
        print("Companion stopped.")
