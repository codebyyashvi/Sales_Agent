# 🎙️ Aria — Real-Time Autonomous AI Voice Sales Agent

> **Production-grade, full-duplex conversational voice sales agent powered by Twilio Bidirectional Media Streams, Gnani Prisma STT, Gnani Timbre TTS, and an adaptive Sales Agent Brain.**

---

## 🌟 Overview & System Architecture

Aria is not a standard turn-based chatbot or simple IVR. It is a full-duplex, low-latency voice agent built specifically for high-converting outbound sales calls.

```
┌────────────────────────────────────────────────────────┐
│             Aria Modern Sales Dashboard                │
│    (Live Audio Waveform, P95 Telemetry, Dial Bar)      │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│               FastAPI Orchestrator                     │
│    (CallSessionManager, Dialogue State Machine)        │
└──────────────┬───────────────────────────▲─────────────┘
               │ Twilio REST API           │ Bidirectional
               ▼ Outbound Call             │ Media Stream WS (8kHz)
┌──────────────────────────┐   ┌───────────┴─────────────┐
│      Customer Phone      │   │  Twilio Media Streams   │
│   (Real Voice Dialogue)  │──►│   (μ-law 8000 Hz Mono)  │
└──────────────────────────┘   └───────────┬─────────────┘
                                           │ Audio Frames
                                           ▼
                               ┌─────────────────────────┐
                               │ Audio Processing Layer  │
                               │  + 2.0s Silence VAD     │
                               └───────────┬─────────────┘
                                           │ Complete Utterance
                                           ▼
                               ┌─────────────────────────┐
                               │       Gnani STT         │
                               │ (Prisma v3, indic-auto) │
                               └───────────┬─────────────┘
                                           │ Recognized Text
                                           ▼
                               ┌─────────────────────────┐
                               │    Sales Agent Brain    │
                               │ (1-3 sentences, safety) │
                               └───────────┬─────────────┘
                                           │ Response Script
                                           ▼
                               ┌─────────────────────────┐
                               │       Gnani TTS         │
                               │ (Timbre v2.5, 8kHz WAV) │
                               └───────────┬─────────────┘
                                           │ Audio Chunks (20ms)
                                           ▼
                               ┌─────────────────────────┐
                               │ μ-law 8kHz Base64 Stream│
                               └───────────┬─────────────┘
                                           │
                                           ▼
                                Customer hears response!
```

---

## ⚡ Key Highlights & Engineering Choices

1. **Twilio Bidirectional Media Streams (`<Connect><Stream>`)**:
   Instead of ordinary Twilio `<Gather>` (which causes unnatural pauses), Aria uses continuous bidirectional streaming over WebSockets. Twilio streams raw 8kHz μ-law audio to our server, and our server streams synthesized 8kHz μ-law audio back into the call in paced 20ms chunks.
2. **Gnani Speech Intelligence**:
   - **STT**: Uses Gnani Prisma v3.0 with automatic Indian language & English detection (`indic-auto`) and dynamic **Product-Specific Vocabulary Boosting** (`key_terms`) to accurately transcribe brand names like `SmartSave+`, `NACH`, `FlexiPay`, and `RuPay`.
   - **TTS**: Uses Gnani Timbre v2.5 (`Nalini` / `Aryan`) generating native 8000 Hz telephony audio with ~280ms first-byte synthesis.
3. **2-Second Voice Activity & Silence Detection**:
   Distinguishes background noise from active speech. Maintains a circular pre-roll buffer to prevent cutting off the first syllable. Triggers utterance completion precisely after 2000ms of sustained post-speech silence.
4. **Instant Barge-in / User Interruption**:
   If the customer speaks while the AI is speaking, the silence detector detects speech onset (`SPEECH_STARTED`), cancels the active TTS audio streaming task, and immediately dispatches a Twilio `clear` event to clear the audio buffer on the customer's phone.
5. **Provider-Agnostic Architecture**:
   STT, TTS, and LLM implementations inherit from base abstract classes (`STTProvider`, `TTSProvider`, `LLMProvider`), allowing hot-swapping between Gnani, Azure OpenAI, standard OpenAI, or local simulated engines.
6. **Strict Sales Safeguards & State Machine**:
   - Max response length: 1 to 3 concise, spoken-aloud sentences.
   - Enforces a 7-stage state machine: `INTRO` ➔ `DISCOVERY` ➔ `PRODUCT_EXPLANATION` ➔ `QUESTIONS` ➔ `OBJECTION_HANDLING` ➔ `BUYING_INTENT` ➔ `CLOSING`.
   - Never hallucinates unverified pricing or warranties.
   - Automatically detects human handoff requests and triggers `HUMAN_HANDOFF`.
7. **Post-Call Analytics & Intelligence**:
   Generates a structured post-call analysis containing Buying Intent Score (0.0 to 1.0), Sentiment, Identified Objections, Executive Summary, and Recommended Next Actions.
8. **Browser Sandbox Mode**:
   Test the entire end-to-end conversational voice pipeline with your laptop microphone and speakers directly from the dashboard!

---

## 🚀 Quickstart Guide

### 1. Requirements
- Python 3.10+
- Twilio Account with Voice capabilities
- Gnani Speech API Key

### 2. Setup Environment
Ensure your `.env` file in the root directory is populated:
```ini
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=+18088004708

GNANI_API_KEY=
GNANI_BASE_URL=https://api.vachana.ai

MONGO_URI=
MONGO_DB_NAME=sales_ai_agent

SILENCE_THRESHOLD_MS=2000
MIN_UTTERANCE_MS=300
```

### 3. Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### 4. Start the Application Server
```bash
python run_server.py
```
Open your browser to: **[http://localhost:8000](http://localhost:8000)**

---

## 📞 Connecting Live Twilio Telephony

1. Start an ngrok tunnel to expose your local server port 8000:
   ```bash
   ngrok http 8000
   ```
2. Copy the resulting HTTPS forwarding URL (e.g. `https://xxxx.ngrok-free.app`) and set it in your `.env`:
   ```ini
   PUBLIC_BASE_URL=https://xxxx.ngrok-free.app
   ```
3. In the **Twilio Console**:
   - Go to **Phone Numbers** ➔ **Manage** ➔ **Active Numbers** ➔ Click your number (`+1 808 800 4708`).
   - Under **Voice Configuration**, set:
     - **A CALL COMES IN**: Webhook
     - **URL**: `https://xxxx.ngrok-free.app/twilio/voice`
     - **HTTP Method**: `POST`
   - Click **Save**.
4. In the Aria Dashboard, select a customer or type a target phone number, and click **Start Outbound Call**!

---

## 🧪 Testing in Browser Sandbox (Without Twilio)

You can demo the voice agent immediately without connecting a phone line:
1. Open [http://localhost:8000](http://localhost:8000).
2. Click **Browser Sandbox** (next to the Start Call button).
3. Allow microphone permissions in your browser.
4. Speak into your microphone! Notice:
   - Voice activity detected in real-time.
   - After you pause for 2.0 seconds, silence detection automatically triggers.
   - Gnani STT transcribes your speech.
   - The Sales Agent Brain generates a contextual 1-2 sentence sales response.
   - Gnani TTS speaks the answer back through your speakers!
   - Interrupting the AI stops playback instantly (Barge-in)!

---

## 📂 Project Directory Structure

```
Sales_Agent/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI application & WebSocket routers
│   │   ├── config.py                # Environment configuration
│   │   ├── database.py              # MongoDB async connection & seeds
│   │   ├── audio/
│   │   │   ├── codec.py             # μ-law <-> PCM, WAV packing, RMS VAD
│   │   │   ├── buffer.py            # Utterance audio buffer & pre-roll
│   │   │   └── resampler.py         # Sample rate converter
│   │   ├── services/
│   │   │   ├── providers/
│   │   │   │   ├── base.py          # Abstract STT/TTS/LLM Provider interfaces
│   │   │   │   ├── stt_gnani.py     # Gnani Prisma v3.0 STT integration
│   │   │   │   ├── tts_gnani.py     # Gnani Timbre v2.5 TTS integration
│   │   │   │   └── llm_provider.py  # Sales Agent Brain & Azure OpenAI
│   │   │   ├── twilio_service.py    # Twilio REST API & TwiML generation
│   │   │   ├── silence_detector.py  # 2.0-sec Silence & Speech onset detector
│   │   │   ├── conversation_service.py # State machine, prompts, objections
│   │   │   └── call_session_manager.py # Call session lifecycle & telemetry
│   │   ├── api/
│   │   │   ├── calls.py             # Call dispatch & Twilio webhook handlers
│   │   │   ├── customers.py         # Customer CRM CRUD
│   │   │   ├── products.py          # Product Knowledge Base CRUD
│   │   │   └── analytics.py         # Aggregated telemetry & benchmarks
│   │   ├── websocket/
│   │   │   ├── twilio_stream.py     # Twilio Media Streams bidirectional WS
│   │   │   └── browser_stream.py    # Browser microphone sandbox WS
│   │   └── schemas/                 # Pydantic request/response models
│   └── requirements.txt
├── frontend/
│   └── index.html                   # Modern glassmorphism dashboard SPA
├── tests/
│   ├── test_audio.py                # Audio codec unit tests
│   ├── test_silence_detector.py     # Silence detection & VAD unit tests
│   └── test_conversation.py        # Sales conversation & state machine tests
├── run_server.py                    # Server launch script
├── .env                             # Environment variables (configured)
├── .env.example                     # Environment template
└── README.md
```

