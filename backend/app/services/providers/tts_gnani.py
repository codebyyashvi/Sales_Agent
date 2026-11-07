import time
import logging
import httpx
from typing import Optional
from app.config import settings
from app.services.providers.base import TTSProvider, TTSResult

logger = logging.getLogger("sales_agent.gnani_tts")

class GnaniTTSProvider(TTSProvider):
    """
    Gnani Timbre v2.5 Text-to-Speech Provider.
    Synthesizes natural, telephony-optimized speech in 8000 Hz 16-bit PCM WAV.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        voice: Optional[str] = None,
        model: Optional[str] = None,
        language: Optional[str] = None
    ):
        self.api_key = api_key or settings.GNANI_API_KEY
        self.base_url = (base_url or settings.GNANI_BASE_URL).rstrip("/")
        self.voice = voice or settings.GNANI_TTS_VOICE
        self.model = model or settings.GNANI_TTS_MODEL
        self.language = language or settings.GNANI_TTS_LANGUAGE

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        language: Optional[str] = None,
        speed: float = 1.0
    ) -> TTSResult:
        if not text or not text.strip():
            return TTSResult(wav_bytes=b"", sample_rate=8000, latency_ms=0.0)

        cleaned_text = text.strip()
        endpoint = f"{self.base_url}/api/v1/tts/inference"
        start_time = time.perf_counter()

        headers = {
            "X-API-Key-ID": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AntigravitySalesVoice/1.0"
        }

        payload = {
            "text": cleaned_text,
            "voice": voice or self.voice,
            "model": self.model,
            "language": language or self.language,
            "speed": speed,
            "audio_config": {
                "encoding": "linear_pcm",
                "container": "wav",
                "num_channels": 1,
                "sample_rate": settings.AUDIO_SAMPLE_RATE,
                "sample_width": 2
            }
        }

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
                latency_ms = (time.perf_counter() - start_time) * 1000

                if response.status_code == 200:
                    wav_bytes = response.content
                    logger.info(
                        f"[Gnani TTS] Synthesized {len(wav_bytes)} bytes audio in {latency_ms:.1f}ms "
                        f"for text: '{cleaned_text[:40]}...'"
                    )
                    return TTSResult(
                        wav_bytes=wav_bytes,
                        sample_rate=settings.AUDIO_SAMPLE_RATE,
                        latency_ms=round(latency_ms, 2)
                    )
                else:
                    logger.error(
                        f"[Gnani TTS] Error {response.status_code}: {response.text}"
                    )
                    return TTSResult(wav_bytes=b"", sample_rate=8000, latency_ms=round(latency_ms, 2))

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"[Gnani TTS] Exception during synthesis: {e}")
            return TTSResult(wav_bytes=b"", sample_rate=8000, latency_ms=round(latency_ms, 2))

