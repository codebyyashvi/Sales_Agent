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

    Handles Gnani TTS WAV files that use a streaming/unknown size header
    (RIFF chunk size = 0xFFFFFFFF). Python's wave module misreports nframes
    as 2^31-1 in that case, so we compute the actual PCM size from the file
    size minus the 44-byte standard WAV header when this is detected.
    """
    buffer = io.BytesIO(wav_bytes)
    with wave.open(buffer, 'rb') as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        reported_frames = wf.getnframes()

        # Detect streaming WAV header: RIFF/data chunk size = 0xFFFFFFFF
        # In that case, compute actual frames from actual byte length
        MAX_WAVE_SIZE = 0x7FFFFFFF  # 2^31 - 1, what wave module reports for 0xFFFFFFFF
        if reported_frames >= MAX_WAVE_SIZE:
            # Skip the standard 44-byte WAV header and treat rest as raw PCM
            header_size = 44
            pcm_data = wav_bytes[header_size:]
            bytes_per_frame = sampwidth * channels
            actual_frames = len(pcm_data) // bytes_per_frame
            frames = pcm_data[:actual_frames * bytes_per_frame]
        else:
            frames = wf.readframes(reported_frames)

        return frames, framerate, channels, sampwidth

def base64_to_mulaw(payload: str) -> bytes:
    """Decode base64 encoded audio from Twilio media message."""
    return base64.b64decode(payload)

def mulaw_to_base64(mulaw_bytes: bytes) -> str:
    """Encode μ-law audio bytes to base64 string for Twilio media message."""
    return base64.b64encode(mulaw_bytes).decode('utf-8')

