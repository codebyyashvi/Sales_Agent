import uuid
import time
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Request, Response, Query
from app.schemas.call import CallStartRequest, CallStartResponse, CallDetail
from app.services.call_session_manager import session_manager
from app.services.twilio_service import twilio_service
from app.websocket.twilio_stream import broadcast_to_dashboards
from app.database import get_db
from app.config import settings

logger = logging.getLogger("sales_agent.api.calls")
router = APIRouter()

# Rate limiting map: phone -> last_called_timestamp
recent_calls = {}

@router.post("/api/calls/start", response_model=CallStartResponse)
async def start_call(payload: CallStartRequest, request: Request):
    phone = payload.phone_number.strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required.")

    # Rate limiting protection: Prevent repeated rapid calls to the same phone number within 15 seconds
    now = time.time()
    last_call = recent_calls.get(phone, 0)
    if now - last_call < 15:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: A call was already initiated to {phone} recently. Please wait a moment."
        )
    recent_calls[phone] = now

    call_id = f"call_{uuid.uuid4().hex[:8]}"

    # Verify customer and product
    db = get_db()
    customer_data = {"customer_id": payload.customer_id, "name": "Valued Customer"}
    product_data = {"product_id": payload.product_id, "name": "SmartSave+"}

    if db is not None:
        c_doc = await db.customers.find_one({"customer_id": payload.customer_id})
        if c_doc:
            customer_data = c_doc
        p_doc = await db.products.find_one({"product_id": payload.product_id})
        if p_doc:
            product_data = p_doc

    # Create session
    session = session_manager.create_session(
        call_id=call_id,
        phone_number=phone,
        customer_id=payload.customer_id,
        product_id=payload.product_id
    )
    session.customer_data = customer_data
    session.product_data = product_data

    # Check if this is a browser test call or a real Twilio telephony call
    if phone.lower().startswith("browser") or phone == "+0000000000":
        logger.info(f"Initialized browser voice call session {call_id}")
        await broadcast_to_dashboards("call_started", session.to_dict())
        return CallStartResponse(
            call_id=call_id,
            call_sid=f"browser_{call_id}",
            status="initiated",
            message="Browser call session initialized. Connect microphone to begin conversation.",
            created_at=time.strftime("%Y-%m-%d %H:%M:%S")
        )

    # Twilio outbound call
    # Determine public host for webhook
    host = request.headers.get("host", "localhost:8000")
    protocol = "https" if "https" in str(request.url) else "http"
    public_url = settings.PUBLIC_BASE_URL or f"{protocol}://{host}"

    logger.info(f"Triggering Twilio call to {phone} via base url {public_url}...")
    res = twilio_service.initiate_call(
        to_phone=phone,
        call_id=call_id,
        customer_id=payload.customer_id,
        product_id=payload.product_id,
        public_url=public_url
    )

    if not res.get("success"):
        session.status = "CALL_FAILED"
        err = res.get("error", "Failed to initiate outbound call.")
        # If unverified number on trial account, provide informative message
        if "unverified" in err.lower() or "21210" in err:
            err_msg = (
                f"Twilio Trial Restriction: The phone number {phone} is not verified on your Twilio account. "
                "Please verify it in the Twilio Console (Phone Numbers > Verified Caller IDs), or use the Browser Simulator."
            )
        else:
            err_msg = f"Twilio Call Error: {err}"
        
        logger.warning(err_msg)
        return CallStartResponse(
            call_id=call_id,
            call_sid=None,
            status="failed",
            message=err_msg,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S")
        )

    session.call_sid = res.get("call_sid")
    if session.call_sid:
        session_manager.sid_map[session.call_sid] = call_id

    await broadcast_to_dashboards("call_started", session.to_dict())

    return CallStartResponse(
        call_id=call_id,
        call_sid=session.call_sid,
        status="ringing",
        message=f"Outbound AI sales call initiated to {phone}.",
        created_at=time.strftime("%Y-%m-%d %H:%M:%S")
    )

@router.post("/twilio/voice")
@router.get("/twilio/voice")
async def twilio_voice_webhook(request: Request, call_id: Optional[str] = Query(None)):
    """
    Returns TwiML instructing Twilio to establish bidirectional Media Stream
    with our /ws/twilio-media WebSocket.
    """
    host = request.headers.get("host", f"{settings.SERVER_HOST}:{settings.SERVER_PORT}")
    # Check if HTTPS / WSS
    is_secure = "https" in str(request.base_url) or "ngrok" in host
    
    # If call_id was not in query, generate or check params
    cid = call_id or f"call_{uuid.uuid4().hex[:8]}"
    twiml_xml = twilio_service.generate_twiml(host=host, call_id=cid, is_secure=is_secure)

    logger.info(f"Served TwiML to Twilio for call_id={cid}: {twiml_xml[:100]}...")
    return Response(content=twiml_xml, media_type="application/xml")

@router.post("/twilio/status")
async def twilio_status_callback(request: Request, call_id: Optional[str] = Query(None)):
    """Twilio call lifecycle callback."""
    form_data = await request.form()
    call_status = form_data.get("CallStatus")
    call_sid = form_data.get("CallSid")

    logger.info(f"[Twilio Status] call_sid={call_sid}, status={call_status}, call_id={call_id}")
    
    session = session_manager.get_session(call_id) if call_id else None
    if not session and call_sid:
        session = session_manager.get_by_call_sid(call_sid)

    if session:
        if call_status == "ringing":
            session.status = "CALL_RINGING"
        elif call_status == "in-progress":
            session.status = "CALL_ACTIVE"
        elif call_status in ["completed", "busy", "no-answer", "failed", "canceled"]:
            await session_manager.end_session(session.call_id, status=f"CALL_{call_status.upper()}")
            await broadcast_to_dashboards("call_ended", session.to_dict())

    return {"status": "received"}

@router.get("/api/calls")
async def list_calls(limit: int = 20):
    """Retrieve call history from active memory and MongoDB."""
    results = []
    # Include active sessions first
    for s in list(session_manager.active_sessions.values())[::-1]:
        results.append(s.to_dict())

    db = get_db()
    if db is not None:
        try:
            cursor = db.calls.find({}, {"_id": 0}).sort("start_time", -1).limit(limit)
            db_calls = await cursor.to_list(length=limit)
            active_ids = {r["call_id"] for r in results}
            for dbc in db_calls:
                if dbc.get("call_id") not in active_ids:
                    results.append(dbc)
        except Exception as e:
            logger.warning(f"Error fetching calls from MongoDB: {e}")

    return results[:limit]

@router.get("/api/calls/{call_id}")
async def get_call_details(call_id: str):
    """Get full details, transcript, and post-call analytics for a specific call."""
    session = session_manager.get_session(call_id)
    if session:
        return session.to_dict()

    db = get_db()
    if db is not None:
        call_doc = await db.calls.find_one({"call_id": call_id}, {"_id": 0})
        if call_doc:
            return call_doc

    raise HTTPException(status_code=404, detail=f"Call session {call_id} not found.")

@router.post("/api/calls/{call_id}/end")
async def end_call(call_id: str):
    """Force end a call session from the dashboard."""
    session = session_manager.get_session(call_id)
    if not session:
        raise HTTPException(status_code=404, detail="Active call session not found.")

    await session_manager.end_session(call_id, status="CALL_ENDED_BY_USER")
    await broadcast_to_dashboards("call_ended", session.to_dict())
    return {"status": "ended", "call_id": call_id}

