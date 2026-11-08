from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class STTResult(BaseModel):
    text: str
    detected_language: Optional[str] = None
    confidence: Optional[float] = 1.0
    latency_ms: float = 0.0

class STTProvider(ABC):
    @abstractmethod
    async def transcribe(
        self,
        pcm_bytes: bytes,
        sample_rate: int = 8000,
        key_terms: Optional[List[str]] = None
    ) -> STTResult:
        """Transcribe raw PCM audio to text."""
        pass

class TTSResult(BaseModel):
    wav_bytes: bytes
    sample_rate: int
    latency_ms: float = 0.0

class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        language: Optional[str] = None,
        speed: float = 1.0
    ) -> TTSResult:
        """Synthesize text into WAV audio bytes."""
        pass

class LLMResponse(BaseModel):
    content: str
    latency_ms: float = 0.0
    tokens_used: int = 0

class LLMProvider(ABC):
    @abstractmethod
    async def generate_reply(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        temperature: float = 0.6,
        agent_profile: Optional[Dict[str, Any]] = None
    ) -> LLMResponse:
        """Generate conversational reply for the sales call."""
        pass

    @abstractmethod
    async def analyze_call(
        self,
        transcript: List[Dict[str, Any]],
        product_name: str,
        customer_name: str
    ) -> Dict[str, Any]:
        """Produce structured JSON post-call analytics and summary."""
        pass

