from app.services.providers.base import STTProvider, TTSProvider, LLMProvider
from app.services.providers.stt_gnani import GnaniSTTProvider
from app.services.providers.tts_gnani import GnaniTTSProvider
from app.services.providers.llm_provider import GroqLLMProvider, AzureOpenAIProvider

_stt_instance: STTProvider = GnaniSTTProvider()
_tts_instance: TTSProvider = GnaniTTSProvider()
_llm_instance: LLMProvider = GroqLLMProvider()

def get_stt_provider() -> STTProvider:
    return _stt_instance

def get_tts_provider() -> TTSProvider:
    return _tts_instance

def get_llm_provider() -> LLMProvider:
    return _llm_instance

