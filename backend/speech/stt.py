import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "").strip()

async def transcribe_audio_file(file_path: str, language_code: str = "en-IN") -> str:
    """
    Transcribe a local audio file using Sarvam AI's Saaras v3 model.
    """
    if not SARVAM_API_KEY:
        raise ValueError("Sarvam API key is not configured.")
        
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")
        
    url = "https://api.sarvam.ai/speech-to-text"
    headers = {
        "api-subscription-key": SARVAM_API_KEY
    }
    
    # Construct multipart form data
    data = aiohttp.FormData()
    data.add_field('model', 'saaras:v3')
    data.add_field('mode', 'transcribe')
    data.add_field('language_code', language_code)
    
    # Read file bytes
    with open(file_path, 'rb') as f:
        file_bytes = f.read()
        data.add_field('file', file_bytes, filename=os.path.basename(file_path), content_type='audio/wav')
        
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data, headers=headers) as response:
            if response.status == 200:
                result = await response.json()
                return result.get("transcript", "")
            else:
                error_text = await response.text()
                raise Exception(f"Sarvam STT API error (status {response.status}): {error_text}")
                
async def transcribe_audio_bytes(audio_bytes: bytes, filename: str = "audio.wav", language_code: str = "en-IN") -> str:
    """
    Transcribe raw audio bytes using Sarvam AI's Saaras v3 model.
    """
    if not SARVAM_API_KEY:
        raise ValueError("Sarvam API key is not configured.")
        
    url = "https://api.sarvam.ai/speech-to-text"
    headers = {
        "api-subscription-key": SARVAM_API_KEY
    }
    
    data = aiohttp.FormData()
    data.add_field('model', 'saaras:v3')
    data.add_field('mode', 'transcribe')
    data.add_field('language_code', language_code)
    data.add_field('file', audio_bytes, filename=filename, content_type='audio/wav')
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data, headers=headers) as response:
            if response.status == 200:
                result = await response.json()
                return result.get("transcript", "")
            else:
                error_text = await response.text()
                raise Exception(f"Sarvam STT API error (status {response.status}): {error_text}")

def pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000, num_channels: int = 1) -> bytes:
    """
    Helper to convert raw 16-bit PCM bytes to a standard RIFF WAV buffer in memory.
    """
    import io
    import wave
    
    wav_buf = io.BytesIO()
    with wave.open(wav_buf, 'wb') as wav_file:
        wav_file.setnchannels(num_channels)
        wav_file.setsampwidth(2) # 16-bit PCM is 2 bytes per sample
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
        
    return wav_buf.getvalue()

