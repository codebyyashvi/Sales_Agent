from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class CallStartRequest(BaseModel):
    phone_number: str = Field(..., description="Target phone number (e.g. +91XXXXXXXXXX or +1XXXXXXXXXX)")
    customer_id: Optional[str] = Field(default="cust_rahul", description="Customer ID")
    product_id: Optional[str] = Field(default="prod_smartsave", description="Product ID")
    agent_voice: Optional[str] = Field(default="Nalini", description="Gnani TTS Voice")

class CallStartResponse(BaseModel):
    call_id: str
    call_sid: Optional[str] = None
    status: str
    message: str
    created_at: str

class MessageRecord(BaseModel):
    id: str
    role: str  # 'assistant' or 'user'
    text: str
    timestamp: float
    stt_latency_ms: Optional[float] = None
    llm_latency_ms: Optional[float] = None
    tts_latency_ms: Optional[float] = None
    total_latency_ms: Optional[float] = None

class CallOutcomeSchema(BaseModel):
    outcome: str
    buying_intent: float
    sentiment: str
    objections: List[str]
    summary: str
    recommended_action: str
    follow_up_required: bool

class CallDetail(BaseModel):
    call_id: str
    call_sid: Optional[str] = None
    stream_sid: Optional[str] = None
    phone_number: str
    customer_id: str
    customer_name: Optional[str] = ""
    product_id: str
    product_name: Optional[str] = ""
    status: str
    start_time: float
    end_time: Optional[float] = None
    duration_seconds: int = 0
    state: str = "INTRO"
    transcript: List[Dict[str, Any]] = []
    outcome: Optional[CallOutcomeSchema] = None
    metrics: Dict[str, Any] = {}

