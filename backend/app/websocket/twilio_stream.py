import json
import time
import asyncio
import logging
from typing import Optional, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect

from app.audio.codec import (
    base64_to_mulaw,
    mulaw_to_pcm,
    pcm_to_mulaw,
    mulaw_to_base64,
    wav_to_pcm
)
from app.services.silence_detector import SilenceDetector
from app.services.call_session_manager import session_manager, CallSession, load_session_profiles
from app.services.conversation_service import conversation_service
from app.services.providers import get_stt_provider, get_tts_provider
from app.config import settings

logger = logging.getLogger("sales_agent.twilio_stream")

# Global set of connected dashboard WebSockets for real-time live monitoring
dashboard_subscribers = set()

async def broadcast_to_dashboards(event_type: str, data: Dict[str, Any]):
    """Send live event to all open frontend dashboard monitors."""
    if not dashboard_subscribers:
        return
    message = json.dumps({"type": event_type, "data": data})
    disconnected = set()
    for ws in dashboard_subscribers:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    for ws in disconnected:
        dashboard_subscribers.discard(ws)

def create_silence_detector() -> SilenceDetector:
    return SilenceDetector(
        silence_threshold_ms=settings.SILENCE_THRESHOLD_MS,
        min_utterance_ms=settings.MIN_UTTERANCE_MS,
        energy_threshold=settings.VAD_ENERGY_THRESHOLD,
        sample_rate=settings.AUDIO_SAMPLE_RATE
    )

async def synthesize_for_agent(tts, text: str, session: CallSession):
    """Gnani TTS using the selected agent's voice and language (env defaults otherwise)."""
    agent = session.agent_data or {}
    return await tts.synthesize(
        text,
        voice=agent.get("voice") or None,
        language=agent.get("language") or None
    )

async def stream_audio_to_twilio(
    ws: WebSocket,
    stream_sid: str,
    wav_bytes: bytes,
    session: CallSession
):
    """
    Stream synthesized audio to Twilio Media Stream in standard 20ms chunks.
    Monitors session.is_speaking for barge-in / interruption cancellations.
    """
    if not wav_bytes:
        return

    try:
        raw_pcm, sample_rate, channels, sampwidth = wav_to_pcm(wav_bytes)
        mulaw_audio = pcm_to_mulaw(raw_pcm, sampwidth)
    except Exception as e:
        logger.error(f"Error parsing TTS WAV for Twilio streaming: {e}")
        return

    session.is_speaking = True
    chunk_size = 160  # 160 bytes of 8kHz mu-law audio = 20ms
    delay = 0.020     # 20ms pacing

    logger.info(f"[Twilio Audio Out] Streaming {len(mulaw_audio)} bytes audio to stream {stream_sid}")

    try:
        for i in range(0, len(mulaw_audio), chunk_size):
            if not session.is_speaking:
                logger.info(f"[Twilio Audio Out] Audio streaming cancelled by barge-in for stream {stream_sid}")
                break

            chunk = mulaw_audio[i:i + chunk_size]
            b64_chunk = mulaw_to_base64(chunk)

            media_msg = {
                "event": "media",
                "streamSid": stream_sid,
                "media": {
                    "payload": b64_chunk
                }
            }
            await ws.send_text(json.dumps(media_msg))
            await asyncio.sleep(delay)

    except Exception as e:
        logger.warning(f"Error while sending audio to Twilio: {e}")
    finally:
        session.is_speaking = False

async def handle_twilio_media_stream(websocket: WebSocket):
    """
    Core Twilio Bidirectional Media Stream WebSocket connection handler.
    """
    await websocket.accept()
    logger.info("Twilio Media Stream WebSocket connection accepted.")

    stream_sid: Optional[str] = None
    call_id: Optional[str] = None
    session: Optional[CallSession] = None
    silence_detector = create_silence_detector()

    stt = get_stt_provider()
    tts = get_tts_provider()

    playback_task: Optional[asyncio.Task] = None

    try:
        while True:
            raw_msg = await websocket.receive_text()
            data = json.loads(raw_msg)
            event = data.get("event")

            # 1. Connected Event
            if event == "connected":
                logger.info(f"[Twilio WS] Handshake connected: {data.get('protocol')}")

            # 2. Start Event
            elif event == "start":
                start_info = data.get("start", {})
                stream_sid = data.get("streamSid") or start_info.get("streamSid")
                call_sid = start_info.get("callSid")
                custom_params = start_info.get("customParameters", {})
                call_id = custom_params.get("call_id")

                logger.info(
                    f"[Twilio WS] Stream started: stream_sid={stream_sid}, "
                    f"call_sid={call_sid}, call_id={call_id}"
                )

                # Associate session
                if call_id:
                    session = session_manager.get_session(call_id)
                if not session and call_sid:
                    session = session_manager.get_by_call_sid(call_sid)

                if not session:
                    # Create session dynamically if not pre-initialized
                    call_id = call_id or f"call_{int(time.time())}"
                    session = session_manager.create_session(
                        call_id=call_id,
                        phone_number="Incoming Twilio Stream",
                        customer_id=custom_params.get("customer_id", ""),
                        product_id="",
                        call_sid=call_sid,
                        agent_id=custom_params.get("agent_id") or None
                    )

                session_manager.register_stream(stream_sid, session.call_id)
                await load_session_profiles(session)
                if not session.agent_data:
                    logger.warning(f"[Twilio WS] No agent profile found for call {session.call_id}")

                # Broadcast call started
                await broadcast_to_dashboards("call_started", session.to_dict())

                # Send initial greeting
                greeting = await conversation_service.get_initial_greeting(
                    session.customer_data, session.agent_data
                )
                session.add_message(role="assistant", text=greeting)
                await broadcast_to_dashboards("transcript_update", {
                    "call_id": session.call_id,
                    "message": session.messages[-1]
                })

                # Synthesize greeting speech
                tts_res = await synthesize_for_agent(tts, greeting, session)
                if tts_res.wav_bytes:
                    playback_task = asyncio.create_task(
                        stream_audio_to_twilio(websocket, stream_sid, tts_res.wav_bytes, session)
                    )

            # 3. Media Audio Event (Customer speaking)
            elif event == "media":
                if not session or not stream_sid:
                    continue

                media_payload = data.get("media", {}).get("payload", "")
                if not media_payload:
                    continue

                # Twilio sends 8000 Hz mu-law audio
                mulaw_bytes = base64_to_mulaw(media_payload)
                pcm_chunk = mulaw_to_pcm(mulaw_bytes)

                # Send audio activity to silence detector
                status, audio_utterance, dur_ms = silence_detector.process_frame(pcm_chunk)

                # Barge-in / Interruption Detection
                if status == "SPEECH_STARTED":
                    if session.is_speaking:
                        logger.info(f"[BARGE-IN] User started speaking! Clearing audio on Twilio stream {stream_sid}")
                        session.is_speaking = False
                        session.metrics["interruptions_count"] += 1
                        
                        # Cancel active audio streaming task
                        if playback_task and not playback_task.done():
                            playback_task.cancel()

                        # Send Twilio clear message to flush phone buffer immediately
                        clear_msg = {
                            "event": "clear",
                            "streamSid": stream_sid
                        }
                        await websocket.send_text(json.dumps(clear_msg))
                        await broadcast_to_dashboards("call_barge_in", {
                            "call_id": session.call_id,
                            "timestamp": time.time()
                        })

                # Utterance Complete after 2.0s of silence
                elif status == "UTTERANCE_COMPLETE" and audio_utterance:
                    turn_start_time = time.perf_counter()
                    logger.info(f"[Twilio WS] Utterance complete ({dur_ms}ms). Sending to Gnani STT...")

                    # 1. Gnani STT
                    key_terms = session.agent_data.get("key_terms", [])
                    stt_res = await stt.transcribe(audio_utterance, sample_rate=8000, key_terms=key_terms)
                    
                    user_text = stt_res.text.strip()
                    if not user_text:
                        logger.info("[Twilio WS] STT returned empty transcription. Listening...")
                        continue

                    # Record user message
                    session.add_message(
                        role="user",
                        text=user_text,
                        stt_latency=stt_res.latency_ms
                    )
                    await broadcast_to_dashboards("transcript_update", {
                        "call_id": session.call_id,
                        "message": session.messages[-1]
                    })

                    # 2. Conversation / LLM Brain
                    turn_res = await conversation_service.process_turn(
                        customer=session.customer_data,
                        agent=session.agent_data,
                        history=session.conversation_history,
                        current_state=session.current_state,
                        user_utterance=user_text
                    )

                    reply_text = turn_res["reply_text"]
                    session.current_state = turn_res["new_state"]
                    llm_latency = turn_res["latency_ms"]

                    # 3. Gnani TTS
                    tts_res = await synthesize_for_agent(tts, reply_text, session)
                    total_latency = (time.perf_counter() - turn_start_time) * 1000

                    # Record assistant message
                    session.add_message(
                        role="assistant",
                        text=reply_text,
                        stt_latency=stt_res.latency_ms,
                        llm_latency=llm_latency,
                        tts_latency=tts_res.latency_ms,
                        total_latency=total_latency
                    )
                    await broadcast_to_dashboards("transcript_update", {
                        "call_id": session.call_id,
                        "message": session.messages[-1]
                    })
                    await broadcast_to_dashboards("state_update", {
                        "call_id": session.call_id,
                        "state": session.current_state,
                        "metrics": session.metrics
                    })

                    # 4. Stream response audio back to customer
                    if tts_res.wav_bytes:
                        playback_task = asyncio.create_task(
                            stream_audio_to_twilio(websocket, stream_sid, tts_res.wav_bytes, session)
                        )

            # 4. DTMF Keypress Event
            elif event == "dtmf":
                digit = data.get("dtmf", {}).get("digit")
                logger.info(f"[Twilio WS] DTMF received: {digit}")

            # 5. Stop Event (Call completed/hung up)
            elif event == "stop":
                logger.info(f"[Twilio WS] Stop event received for stream {stream_sid}")
                break

    except WebSocketDisconnect:
        logger.info(f"[Twilio WS] WebSocket disconnected for stream {stream_sid}")
    except Exception as e:
        logger.error(f"[Twilio WS] Error during stream processing: {e}")
    finally:
        if session:
            # Generate post-call analysis
            logger.info(f"Generating post-call analysis for call {session.call_id}...")
            analysis = await conversation_service.generate_post_call_analysis(
                transcript=session.messages,
                agent=session.agent_data,
                customer=session.customer_data
            )
            session.outcome = analysis
            await session_manager.end_session(session.call_id, status="CALL_COMPLETED")
            await broadcast_to_dashboards("call_ended", session.to_dict())

