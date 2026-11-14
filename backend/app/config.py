import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Find project root where .env resides
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Twilio
    TWILIO_ACCOUNT_SID: str = Field(default="", description="Twilio Account SID")
    TWILIO_AUTH_TOKEN: str = Field(default="", description="Twilio Auth Token")
    TWILIO_PHONE_NUMBER: str = Field(default="", description="Twilio Voice Phone Number")

    # Gnani Speech APIs
    GNANI_API_KEY: str = Field(default="", description="Gnani X-API-Key-ID")
    GNANI_BASE_URL: str = Field(default="https://api.vachana.ai", description="Gnani API Base URL")
    GNANI_STT_MODEL: str = Field(default="prisma-v3.0", description="Gnani STT Model")
    GNANI_STT_LANGUAGE: str = Field(default="en-IN", description="Gnani STT Language Code")
    GNANI_TTS_VOICE: str = Field(default="Nalini", description="Gnani TTS Voice")
    GNANI_TTS_MODEL: str = Field(default="timbre-v2.5", description="Gnani TTS Model")
    GNANI_TTS_LANGUAGE: str = Field(default="en-IN", description="Gnani TTS Language")

    # LLM Settings
    LLM_PROVIDER: str = Field(default="groq", description="groq, openai, azure_openai, or mock")
    GROQ_API_KEY: str = Field(default="", description="Groq API Key (gsk_...)")
    GROQ_MODEL: str = Field(default="qwen/qwen3.8-27b", description="Groq Model Name")
    OPEN_AI_DEPLOYMENT_NAME: str = Field(default="gpt-4o-mini", description="Azure OpenAI Deployment Name")
    OPEN_AI_ENDPOINT: str = Field(default="", description="Azure OpenAI Endpoint")
    OPEN_AI_KEY: str = Field(default="", description="Azure OpenAI Key")
    OPEN_AI_API_VERSION: str = Field(default="2024-02-15-preview", description="Azure OpenAI API Version")
    OPENAI_API_KEY: str = Field(default="", description="Standard OpenAI API Key")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini", description="Standard OpenAI Model")

    # Database
    MONGO_URI: str = Field(default="mongodb://localhost:27017", description="MongoDB Connection URI")
    MONGO_DB_NAME: str = Field(default="sales_ai_agent", description="Database Name")

    # Voice / Audio Pipeline
    SILENCE_THRESHOLD_MS: int = Field(default=1000, description="Silence duration in ms to finalize utterance")
    MIN_UTTERANCE_MS: int = Field(default=300, description="Minimum audio duration in ms to treat as speech")
    VAD_ENERGY_THRESHOLD: int = Field(default=300, description="RMS threshold to classify audio as voice activity")
    AUDIO_SAMPLE_RATE: int = Field(default=8000, description="Native phone sample rate in Hz")

    # Server & Webhook
    SERVER_HOST: str = Field(default="0.0.0.0", description="Host to bind server")
    SERVER_PORT: int = Field(default=8000, description="Port to bind server")
    PUBLIC_BASE_URL: str = Field(default="", description="Public base URL for Twilio webhook (e.g. ngrok)")

settings = Settings()

