import sys, asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))
from app.audio.codec import wav_to_pcm

with open('test_tts.wav', 'rb') as f:
    wav_bytes = f.read()

pcm, sr, ch, sw = wav_to_pcm(wav_bytes)
print(f'Input PCM: {len(pcm)} bytes, {sr}Hz, {ch}ch, {sw*8}bit')

from app.services.providers.stt_gnani import GnaniSTTProvider

async def test_stt():
    stt = GnaniSTTProvider()
    res = await stt.transcribe(pcm, sample_rate=sr)
    print(f'STT Status: OK')
    print(f'Transcribed text: "{res.text}"')
    print(f'Latency: {res.latency_ms:.0f}ms')
    print(f'Language: {res.detected_language}')

asyncio.run(test_stt())

