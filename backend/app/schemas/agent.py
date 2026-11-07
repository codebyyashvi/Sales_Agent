from pydantic import BaseModel, Field
from typing import List, Optional


class AgentFAQ(BaseModel):
    q: str = Field(..., description="Question a prospect may ask")
    a: str = Field(..., description="Verified answer the agent should give")


class AgentObjection(BaseModel):
    objection: str = Field(..., description="Objection the prospect may raise (e.g. 'too expensive')")
    response: str = Field(..., description="Approved rebuttal for that objection")


class AgentBase(BaseModel):
    # Identity
    name: str = Field(..., min_length=1, description="Agent name shown in the dashboard")
    description: Optional[str] = Field(default="", description="What this agent is used for")
    persona_name: Optional[str] = Field(default="", description="Name the agent introduces itself with on the call")
    company_name: Optional[str] = Field(default="", description="Company the agent is calling on behalf of")

    # Product knowledge (the ONLY facts the LLM may use)
    product_name: str = Field(..., min_length=1, description="Product or service being sold")
    product_description: str = Field(..., min_length=1, description="Full product overview")
    key_features: List[str] = Field(default_factory=list, description="Core benefits and capabilities")
    pricing: Optional[str] = Field(default="", description="Exact pricing / plans")
    offers: Optional[str] = Field(default="", description="Currently approved discounts or offers")
    target_audience: Optional[str] = Field(default="", description="Who the product is for")
    faqs: List[AgentFAQ] = Field(default_factory=list)
    objections: List[AgentObjection] = Field(default_factory=list)

    # Conversation behaviour
    call_objective: Optional[str] = Field(default="", description="Goal of the call, e.g. 'book a demo'")
    greeting: Optional[str] = Field(
        default="",
        description="Opening line. Supports {customer_name}, {agent_name}, {company_name}, {product_name}",
    )
    closing_message: Optional[str] = Field(default="", description="What to say when wrapping up the call")
    tone: Optional[str] = Field(default="Warm, polite, professional and consultative")
    additional_instructions: Optional[str] = Field(default="", description="Any extra rules for the agent")

    # Voice
    language: Optional[str] = Field(default="", description="Gnani TTS language code, e.g. en-IN, hi-IN")
    voice: Optional[str] = Field(default="", description="Gnani TTS voice name")
    key_terms: List[str] = Field(default_factory=list, description="Vocabulary hints for Gnani STT")


class AgentCreate(AgentBase):
    pass


class AgentUpdate(AgentBase):
    pass


class AgentOut(AgentBase):
    agent_id: str
    created_at: Optional[float] = None
    updated_at: Optional[float] = None
