import unittest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.audio.codec import (
    mulaw_to_pcm,
    pcm_to_mulaw,
    calculate_rms,
    pcm_to_wav,
    wav_to_pcm,
    base64_to_mulaw,
    mulaw_to_base64
)
from app.audio.buffer import AudioUtteranceBuffer

def test_mulaw_pcm_roundtrip():
    # 8kHz 16-bit audio: 16000 bytes per second
    pcm = b"\x00\x00\x10\x00\x20\x00" * 100
    mulaw = pcm_to_mulaw(pcm)
    assert len(mulaw) == len(pcm) // 2
    
    pcm_recovered = mulaw_to_pcm(mulaw)
    assert len(pcm_recovered) == len(pcm)

def test_rms_calculation():
    silence = b"\x00\x00" * 160
    assert calculate_rms(silence) == 0

    loud = b"\x7f\x7f" * 160
    assert calculate_rms(loud) > 1000

def test_wav_container():
    pcm = b"\x00\x00" * 8000  # 1 second silence
    wav_data = pcm_to_wav(pcm, sample_rate=8000)
    assert wav_data.startswith(b"RIFF")
    
    frames, rate, channels, width = wav_to_pcm(wav_data)
    assert rate == 8000
    assert channels == 1
    assert width == 2
    assert len(frames) == len(pcm)

def test_base64_codec():
    data = b"\x01\x02\x03\x04\x05"
    b64 = mulaw_to_base64(data)
    recovered = base64_to_mulaw(b64)
    assert recovered == data

def test_utterance_buffer():
    buf = AudioUtteranceBuffer(sample_rate=8000)
    chunk = b"\x00\x00" * 160  # 20ms of audio = 320 bytes
    
    buf.add_frame(chunk)
    assert not buf.is_recording

    buf.start_utterance(100.0)
    assert buf.is_recording
    buf.add_frame(chunk)
    
    assert buf.get_duration_ms() >= 20
    assert len(buf.get_pcm_bytes()) >= 320
    
    buf.reset()
    assert not buf.is_recording
    assert len(buf.active_chunks) == 0

if __name__ == "__main__":
    test_mulaw_pcm_roundtrip()
    test_rms_calculation()
    test_wav_container()
    test_base64_codec()
    test_utterance_buffer()
    print("All audio unit tests passed successfully!")
