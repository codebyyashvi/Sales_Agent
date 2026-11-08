import sys
from pathlib import Path
import uvicorn

# Ensure backend directory is in Python path
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

if __name__ == "__main__":
    from app.config import settings
    print("=" * 60)
    print("🚀 Starting AI Sales Calling Agent Server")
    print(f"📡 Host: {settings.SERVER_HOST} | Port: {settings.SERVER_PORT}")
    print(f"🎙️ Gnani STT: {settings.GNANI_STT_MODEL} | Voice: {settings.GNANI_TTS_VOICE}")
    print(f"🤖 LLM Provider: {'Groq (' + settings.GROQ_MODEL + ')' if settings.GROQ_API_KEY else 'Agent-Aware Sales Engine'}")
    print(f"📞 Twilio Phone: {settings.TWILIO_PHONE_NUMBER}")
    print(f"🌐 Dashboard URL: http://localhost:{settings.SERVER_PORT}")
    print("=" * 60)
    uvicorn.run("app.main:app", host=settings.SERVER_HOST, port=settings.SERVER_PORT, reload=False)

