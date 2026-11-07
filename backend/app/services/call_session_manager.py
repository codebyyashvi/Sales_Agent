import time
import uuid
import logging
from typing import Dict, Any, Optional, List
from app.database import get_db
from app.services.conversation_service import agent_from_product

logger = logging.getLogger("sales_agent.call_manager")

class CallSession:
    def __init__(
        self,
        call_id: str,
        phone_number: str,
        customer_id: str,
        product_id: str,
        call_sid: Optional[str] = None,
        agent_id: Optional[str] = None
    ):
        self.call_id = call_id
        self.phone_number = phone_number
        self.customer_id = customer_id
        self.product_id = product_id
        self.agent_id = agent_id
        self.call_sid = call_sid
        self.stream_sid: Optional[str] = None

        self.status = "CALL_INITIATED"
        self.current_state = "INTRO"
        self.start_time: float = time.time()
        self.end_time: Optional[float] = None
        self.duration_seconds: int = 0

        self.conversation_history: List[Dict[str, str]] = []
        self.messages: List[Dict[str, Any]] = []
        
        self.is_speaking: bool = False
        self.last_audio_timestamp: float = time.time()
        self.active_tts_task: Optional[Any] = None

        self.customer_data: Dict[str, Any] = {}
        self.product_data: Dict[str, Any] = {}
        # Selected sales agent profile; the only knowledge source for the LLM on this call
        self.agent_data: Dict[str, Any] = {}
        
        self.metrics: Dict[str, Any] = {
            "turns_count": 0,
            "avg_stt_latency_ms": 0.0,
            "avg_llm_latency_ms": 0.0,
            "avg_tts_latency_ms": 0.0,
            "avg_total_latency_ms": 0.0,
            "interruptions_count": 0
        }
        self.outcome: Optional[Dict[str, Any]] = None

    def add_message(
        self,
        role: str,
        text: str,
        stt_latency: float = 0.0,
        llm_latency: float = 0.0,
        tts_latency: float = 0.0,
        total_latency: float = 0.0
    ) -> Dict[str, Any]:
        msg = {
            "id": str(uuid.uuid4()),
            "call_id": self.call_id,
            "role": role,
            "text": text,
            "timestamp": time.time(),
            "stt_latency_ms": round(stt_latency, 2),
            "llm_latency_ms": round(llm_latency, 2),
            "tts_latency_ms": round(tts_latency, 2),
            "total_latency_ms": round(total_latency, 2)
        }
        self.messages.append(msg)
        self.conversation_history.append({"role": role, "content": text})
        
        # Update running latency averages
        if role == "assistant" and total_latency > 0:
            turns = self.metrics["turns_count"] + 1
            self.metrics["turns_count"] = turns
            self.metrics["avg_stt_latency_ms"] = round(
                (self.metrics["avg_stt_latency_ms"] * (turns - 1) + stt_latency) / turns, 1
            )
            self.metrics["avg_llm_latency_ms"] = round(
                (self.metrics["avg_llm_latency_ms"] * (turns - 1) + llm_latency) / turns, 1
            )
            self.metrics["avg_tts_latency_ms"] = round(
                (self.metrics["avg_tts_latency_ms"] * (turns - 1) + tts_latency) / turns, 1
            )
            self.metrics["avg_total_latency_ms"] = round(
                (self.metrics["avg_total_latency_ms"] * (turns - 1) + total_latency) / turns, 1
            )

        return msg

    def to_dict(self) -> Dict[str, Any]:
        dur = int(time.time() - self.start_time) if not self.end_time else self.duration_seconds
        return {
            "call_id": self.call_id,
            "call_sid": self.call_sid,
            "stream_sid": self.stream_sid,
            "phone_number": self.phone_number,
            "customer_id": self.customer_id,
            "customer_name": self.customer_data.get("name", "Unknown"),
            "agent_id": self.agent_id,
            "agent_name": self.agent_data.get("name", ""),
            "product_id": self.product_id,
            "product_name": self.agent_data.get("product_name") or self.product_data.get("name", "Unknown"),
            "status": self.status,
            "state": self.current_state,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": dur,
            "is_speaking": self.is_speaking,
            "transcript": self.messages,
            "metrics": self.metrics,
            "outcome": self.outcome
        }

class CallSessionManager:
    def __init__(self):
        self.active_sessions: Dict[str, CallSession] = {}
        # Map stream_sid -> call_id
        self.stream_map: Dict[str, str] = {}
        # Map call_sid -> call_id
        self.sid_map: Dict[str, str] = {}

    def create_session(
        self,
        call_id: str,
        phone_number: str,
        customer_id: str,
        product_id: str,
        call_sid: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> CallSession:
        session = CallSession(
            call_id=call_id,
            phone_number=phone_number,
            customer_id=customer_id,
            product_id=product_id,
            call_sid=call_sid,
            agent_id=agent_id
        )
        self.active_sessions[call_id] = session
        if call_sid:
            self.sid_map[call_sid] = call_id
        logger.info(f"Created CallSession {call_id} for phone {phone_number}")
        return session

    def get_session(self, call_id: str) -> Optional[CallSession]:
        return self.active_sessions.get(call_id)

    def get_by_stream_sid(self, stream_sid: str) -> Optional[CallSession]:
        call_id = self.stream_map.get(stream_sid)
        return self.active_sessions.get(call_id) if call_id else None

    def get_by_call_sid(self, call_sid: str) -> Optional[CallSession]:
        call_id = self.sid_map.get(call_sid)
        return self.active_sessions.get(call_id) if call_id else None

    def register_stream(self, stream_sid: str, call_id: str):
        self.stream_map[stream_sid] = call_id
        session = self.get_session(call_id)
        if session:
            session.stream_sid = stream_sid
            session.status = "CALL_ACTIVE"
            logger.info(f"Associated Stream SID {stream_sid} with Call ID {call_id}")

    async def end_session(self, call_id: str, status: str = "CALL_ENDED"):
        session = self.get_session(call_id)
        if not session:
            return

        session.status = status
        session.end_time = time.time()
        session.duration_seconds = int(session.end_time - session.start_time)
        session.is_speaking = False

        # Persist to database if available
        db = get_db()
        if db is not None:
            try:
                record = session.to_dict()
                await db.calls.update_one(
                    {"call_id": call_id},
                    {"$set": record},
                    upsert=True
                )
                logger.info(f"Persisted ended call {call_id} to MongoDB.")
            except Exception as e:
                logger.error(f"Failed to persist call {call_id} to MongoDB: {e}")


async def load_session_profiles(session: CallSession):
    """Load customer and agent profiles from MongoDB if they were not attached at call start."""
    db = get_db()
    if db is not None:
        if not session.customer_data and session.customer_id:
            cust = await db.customers.find_one({"customer_id": session.customer_id})
            if cust:
                session.customer_data = cust
        if not session.agent_data and session.agent_id:
            agent = await db.agents.find_one({"agent_id": session.agent_id}, {"_id": 0})
            if agent:
                session.agent_data = agent
        if not session.agent_data and not session.product_data and session.product_id:
            prod = await db.products.find_one({"product_id": session.product_id}, {"_id": 0})
            if prod:
                session.product_data = prod

    if not session.agent_data and session.product_data:
        session.agent_data = agent_from_product(session.product_data)


session_manager = CallSessionManager()

