import audioop
import base64
import io
import wave
from typing import Tuple

def mulaw_to_pcm(mulaw_bytes: bytes, width: int = 2) -> bytes:
    """
    Convert 8-bit G.711 μ-law bytes to 16-bit signed linear PCM bytes.
    width=2 corresponds to 16-bit audio.
    """
    return audioop.ulaw2lin(mulaw_bytes, width)

def pcm_to_mulaw(pcm_bytes: bytes, width: int = 2) -> bytes:
    """
    Convert 16-bit signed linear PCM bytes to 8-bit G.711 μ-law bytes.
    """
    return audioop.lin2ulaw(pcm_bytes, width)

def calculate_rms(pcm_bytes: bytes, width: int = 2) -> int:
    """
    Calculate the Root Mean Square (RMS) energy of a linear PCM audio chunk.
    Used for Voice Activity Detection (VAD) and silence detection.
    """
    if not pcm_bytes:
        return 0
    try:
        return audioop.rms(pcm_bytes, width)
    except Exception:
        return 0

def pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 8000, channels: int = 1, width: int = 2) -> bytes:
    """
    Encapsulate raw linear PCM bytes into a standard RIFF/WAV container.
    Gnani STT accepts WAV audio with RIFF header.
    """
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buffer.getvalue()

def wav_to_pcm(wav_bytes: bytes) -> Tuple[bytes, int, int, int]:
    """
    Extract raw PCM frames and format metadata (sample_rate, channels, sampwidth) from a WAV container.
    """
    buffer = io.BytesIO(wav_bytes)
    with wave.open(buffer, 'rb') as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
        return frames, framerate, channels, sampwidth

def base64_to_mulaw(payload: str) -> bytes:
    """Decode base64 encoded audio from Twilio media message."""
    return base64.b64decode(payload)

def mulaw_to_base64(mulaw_bytes: bytes) -> str:
    """Encode μ-law audio bytes to base64 string for Twilio media message."""
    return base64.b64encode(mulaw_bytes).decode('utf-8')

