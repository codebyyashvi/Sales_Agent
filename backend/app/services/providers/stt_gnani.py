import time
import logging
import httpx
from typing import List, Optional
from app.config import settings
from app.audio.codec import pcm_to_wav
from app.services.providers.base import STTProvider, STTResult

logger = logging.getLogger("sales_agent.gnani_stt")

class GnaniSTTProvider(STTProvider):
    """
    Gnani Prisma v3.0 Speech-to-Text Provider.
    Accepts raw PCM audio, wraps into a WAV container, sends to
    https://api.vachana.ai/stt/v3, and returns recognized text.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        language: Optional[str] = None
    ):
        self.api_key = api_key or settings.GNANI_API_KEY
        self.base_url = (base_url or settings.GNANI_BASE_URL).rstrip("/")
        self.model = model or settings.GNANI_STT_MODEL
        self.language = language or settings.GNANI_STT_LANGUAGE

    async def transcribe(
        self,
        pcm_bytes: bytes,
        sample_rate: int = 8000,
        key_terms: Optional[List[str]] = None
    ) -> STTResult:
        if not pcm_bytes:
            return STTResult(text="", latency_ms=0.0)

        wav_data = pcm_to_wav(pcm_bytes, sample_rate=sample_rate, channels=1, width=2)
        start_time = time.perf_counter()
        endpoint = f"{self.base_url}/stt/v3"

        headers = {
            "X-API-Key-ID": self.api_key,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AntigravitySalesVoice/1.0"
        }

        form_data = {
            "model": self.model,
            "language_code": self.language
        }
        
        # Add key_terms if provided to boost domain & product recognition
        if key_terms:
            form_data["key_terms"] = ",".join(key_terms)

        files = {
            "audio_file": ("speech.wav", wav_data, "audio/wav")
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    data=form_data,
                    files=files
                )
                latency_ms = (time.perf_counter() - start_time) * 1000

                if response.status_code == 200:
                    data = response.json()
                    transcript = data.get("transcript", "").strip()
                    detected_lang = data.get("detected_language_code")
                    logger.info(
                        f"[Gnani STT] Transcription Success: '{transcript}' "
                        f"(Lang: {detected_lang}, Latency: {latency_ms:.1f}ms)"
                    )
                    return STTResult(
                        text=transcript,
                        detected_language=detected_lang,
                        confidence=1.0,
                        latency_ms=round(latency_ms, 2)
                    )
                else:
                    logger.error(
                        f"[Gnani STT] Error {response.status_code}: {response.text}"
                    )
                    return STTResult(text="", latency_ms=round(latency_ms, 2))

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"[Gnani STT] Exception during transcription: {e}")
            return STTResult(text="", latency_ms=round(latency_ms, 2))

