import json
import time
import asyncio
import logging
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect

from app.audio.codec import wav_to_pcm, calculate_rms
from app.audio.resampler import resample_pcm
from app.services.silence_detector import SilenceDetector
from app.services.call_session_manager import session_manager, CallSession
from app.services.conversation_service import conversation_service
from app.services.providers import get_stt_provider, get_tts_provider
from app.websocket.twilio_stream import dashboard_subscribers, broadcast_to_dashboards
from app.database import get_db

logger = logging.getLogger("sales_agent.browser_stream")

async def handle_dashboard_websocket(websocket: WebSocket):
    """
    Connects frontend dashboard for real-time monitoring and event subscriptions.
    """
    await websocket.accept()
    dashboard_subscribers.add(websocket)
    logger.info("Dashboard WebSocket client connected.")

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            # Handle ping/heartbeat
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "time": time.time()}))
    except WebSocketDisconnect:
        dashboard_subscribers.discard(websocket)
        logger.info("Dashboard WebSocket client disconnected.")
    except Exception as e:
        dashboard_subscribers.discard(websocket)
        logger.warning(f"Dashboard WS error: {e}")

async def handle_browser_voice_stream(websocket: WebSocket, call_id: str):
    """
    Allows full bidirectional live voice conversation directly in the web browser
    using Web Audio API (PCM chunks), passing through the identical
    Silence Detector -> Gnani STT -> LLM Brain -> Gnani TTS -> Audio Playback pipeline!
    """
    await websocket.accept()
    logger.info(f"Browser Voice Stream connected for call_id: {call_id}")

    session = session_manager.get_session(call_id)
    if not session:
        session = session_manager.create_session(
            call_id=call_id,
            phone_number="Browser Voice Test",
            customer_id="cust_rahul",
            product_id="prod_smartsave"
        )

    db = get_db()
    if db is not None:
        cust = await db.customers.find_one({"customer_id": session.customer_id})
        if cust:
            session.customer_data = cust
        prod = await db.products.find_one({"product_id": session.product_id})
        if prod:
            session.product_data = prod

    stt = get_stt_provider()
    tts = get_tts_provider()
    silence_detector = SilenceDetector(silence_threshold_ms=2000, min_utterance_ms=300, sample_rate=8000)

    # Send initial greeting
    greeting = await conversation_service.get_initial_greeting(session.customer_data, session.product_data)
    session.add_message(role="assistant", text=greeting)
    await broadcast_to_dashboards("transcript_update", {"call_id": session.call_id, "message": session.messages[-1]})

    # Synthesize greeting
    tts_res = await tts.synthesize(greeting)
    if tts_res.wav_bytes:
        session.is_speaking = True
        await websocket.send_bytes(tts_res.wav_bytes)
        session.is_speaking = False

    try:
        while True:
            # Receive binary audio chunk from browser microphone (16-bit 8000Hz or 16000Hz PCM)
            message = await websocket.receive()
            if "bytes" in message and message["bytes"]:
                pcm_data = message["bytes"]
                
                # Check RMS energy
                rms = calculate_rms(pcm_data)
                
                # Send energy info to dashboard for live waveform
                await broadcast_to_dashboards("audio_energy", {
                    "call_id": session.call_id,
                    "rms": rms,
                    "is_speaking": session.is_speaking
                })

                status, utterance_audio, dur_ms = silence_detector.process_frame(pcm_data)

                # Interruption / Barge-in
                if status == "SPEECH_STARTED" and session.is_speaking:
                    session.is_speaking = False
                    session.metrics["interruptions_count"] += 1
                    await websocket.send_text(json.dumps({"type": "interrupt"}))
                    await broadcast_to_dashboards("call_barge_in", {"call_id": session.call_id})

                # Utterance complete (2 sec silence)
                elif status == "UTTERANCE_COMPLETE" and utterance_audio:
                    turn_start = time.perf_counter()
                    
                    # 1. Gnani STT
                    stt_res = await stt.transcribe(
                        utterance_audio,
                        sample_rate=8000,
                        key_terms=session.product_data.get("key_terms", [])
                    )
                    user_text = stt_res.text.strip()
                    if not user_text:
                        continue

                    session.add_message(role="user", text=user_text, stt_latency=stt_res.latency_ms)
                    await broadcast_to_dashboards("transcript_update", {
                        "call_id": session.call_id,
                        "message": session.messages[-1]
                    })

                    # 2. LLM Brain
                    turn_res = await conversation_service.process_turn(
                        customer=session.customer_data,
                        product=session.product_data,
                        history=session.conversation_history,
                        current_state=session.current_state,
                        user_utterance=user_text
                    )
                    reply_text = turn_res["reply_text"]
                    session.current_state = turn_res["new_state"]

                    # 3. Gnani TTS
                    tts_res = await tts.synthesize(reply_text)
                    total_lat = (time.perf_counter() - turn_start) * 1000

                    session.add_message(
                        role="assistant",
                        text=reply_text,
                        stt_latency=stt_res.latency_ms,
                        llm_latency=turn_res["latency_ms"],
                        tts_latency=tts_res.latency_ms,
                        total_latency=total_lat
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

                    # 4. Stream audio bytes to browser speaker
                    if tts_res.wav_bytes:
                        session.is_speaking = True
                        await websocket.send_bytes(tts_res.wav_bytes)
                        session.is_speaking = False

            elif "text" in message:
                text_data = json.loads(message["text"])
                if text_data.get("type") == "end_call":
                    break

    except WebSocketDisconnect:
        logger.info(f"Browser voice stream disconnected for call {call_id}")
    except Exception as e:
        logger.error(f"Error in browser voice stream: {e}")
    finally:
        analysis = await conversation_service.generate_post_call_analysis(
            transcript=session.messages,
            product=session.product_data,
            customer=session.customer_data
        )
        session.outcome = analysis
        await session_manager.end_session(session.call_id, status="CALL_COMPLETED")
        await broadcast_to_dashboards("call_ended", session.to_dict())

