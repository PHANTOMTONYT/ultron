import os
import aiohttp
import base64
import edge_tts
from dotenv import load_dotenv

load_dotenv()

# Get settings
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "").strip()
DEFAULT_VOICE = "en-IN-NeerjaNeural"

async def text_to_speech_sarvam(text: str, language_code: str = "en-IN", speech_format: str = "mp3") -> str:
    """
    Synthesize speech using Sarvam AI's Bulbul v3 model.
    Returns base64-encoded audio (format: mp3 or wav).
    """
    if not SARVAM_API_KEY:
        raise ValueError("Sarvam API key is not configured.")
        
    url = "https://api.sarvam.ai/text-to-speech"
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Map input text language. For companion, we default to English/Hindi mixed.
    payload = {
        "text": text,
        "target_language_code": language_code,
        "speaker": "shubh",
        "model": "bulbul:v3",
        "output_audio_codec": speech_format
    }
    
    if speech_format == "wav":
        payload["sample_rate"] = 16000
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                if "audios" in data and len(data["audios"]) > 0:
                    # Sarvam returns an array of base64 audio strings
                    return data["audios"][0]
                else:
                    raise Exception("No audio returned in Sarvam response.")
            else:
                error_text = await response.text()
                raise Exception(f"Sarvam API error (status {response.status}): {error_text}")

async def text_to_speech_edge(text: str, voice: str = DEFAULT_VOICE) -> str:
    """
    Fallback method using edge-tts.
    Synthesizes speech and returns it as a base64 string.
    """
    # Initialize edge_tts
    communicate = edge_tts.Communicate(text, voice)
    
    # We buffer the stream into memory bytes
    audio_data = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data.extend(chunk["data"])
            
    if not audio_data:
        raise Exception("Edge-TTS generated empty audio.")
        
    # Convert to base64 string
    base64_audio = base64.b64encode(audio_data).decode("utf-8")
    return base64_audio

async def synthesize_speech(text: str, language_code: str = "en-IN", speech_format: str = "mp3") -> str:
    """
    Synthesizes text to speech, trying Sarvam AI first and falling back to Edge-TTS.
    Returns base64 audio string.
    """
    if SARVAM_API_KEY:
        try:
            print(f"TTS: Synthesizing using Sarvam AI ({speech_format}, lang: {language_code})...")
            # Sarvam expects lang code like hi-IN, en-IN, etc.
            return await text_to_speech_sarvam(text, language_code, speech_format)
        except Exception as e:
            print(f"TTS: Sarvam AI synthesis failed ({e}). Falling back to Edge-TTS...")
            
    # Fallback to edge tts
    try:
        print(f"TTS: Synthesizing using Edge-TTS...")
        # Map language code to edge-tts voices
        edge_voice = DEFAULT_VOICE
        if "hi" in language_code.lower():
            edge_voice = "hi-IN-MadhurNeural"
        return await text_to_speech_edge(text, edge_voice)
    except Exception as e:
        print(f"TTS: Edge-TTS synthesis failed: {e}")
        raise e
