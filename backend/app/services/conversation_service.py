import logging
from typing import Dict, List, Any, Optional
from app.services.providers import get_llm_provider

logger = logging.getLogger("sales_agent.conversation")

# Sales Conversation State Machine
CONVERSATION_STATES = [
    "INTRO",
    "DISCOVERY",
    "PRODUCT_EXPLANATION",
    "QUESTIONS",
    "OBJECTION_HANDLING",
    "BUYING_INTENT",
    "CLOSING"
]

TERMINAL_STATES = [
    "CUSTOMER_NOT_INTERESTED",
    "CALLBACK_REQUESTED",
    "HUMAN_HANDOFF",
    "CONVERTED",
    "CUSTOMER_HUNG_UP"
]

class ConversationService:
    def __init__(self):
        self.llm = get_llm_provider()

    def build_system_prompt(self, customer: Dict[str, Any], product: Dict[str, Any], current_state: str) -> str:
        """
        Construct a strict, production-grade system prompt with injected
        customer profile, verified product knowledge, and voice synthesis constraints.
        """
        features_list = "\n".join([f"- {f}" for f in product.get("features", [])])
        faqs_list = "\n".join([f"Q: {item.get('q')}\nA: {item.get('a')}" for item in product.get("faqs", [])])
        objections_dict = "\n".join([f"- If customer raises '{k}': Rebuttal: {v}" for k, v in product.get("objections", {}).items()])

        return f"""You are 'Aria', an elite, polite, and persuasive AI sales representative calling on behalf of {product.get('name', 'our company')}.

### CUSTOMER PROFILE:
- Name: {customer.get('name', 'Valued Customer')}
- Company: {customer.get('company', 'their organization')}
- Designation: {customer.get('designation', 'Decision Maker')}
- Background Notes: {customer.get('notes', 'Interested in modern solutions.')}

### VERIFIED PRODUCT KNOWLEDGE ({product.get('name')}):
- Tagline: {product.get('tagline', '')}
- Description: {product.get('description', '')}
- Verified Features:
{features_list}
- Strict Pricing: {product.get('pricing', 'Contact sales')}
- Verified FAQs:
{faqs_list}
- Predefined Objection Handling Playbook:
{objections_dict}

### STRICT BUSINESS & SAFETY RULES:
1. ONLY discuss information provided in the product knowledge above.
2. NEVER invent discounts, custom interest rates, warranties, or contractual terms. If the user asks for something not in the knowledge base, state: "I don't want to give you incorrect information. I can arrange for a senior representative to confirm those specific details for you."
3. Maximum response length: EXACTLY 1 TO 3 SHORT SENTENCES. This will be spoken aloud to the customer over phone telephony. Never write bullet points, long paragraphs, or Markdown formatting.
4. Keep the tone warm, consultative, respectful, and articulate.
5. If the customer indicates interest or agreement, transition toward securing a trial account or follow-up demo.
6. If the customer explicitly asks for a human or manager, respond politely that you will connect them to a senior representative immediately.
7. Current Sales Stage: [{current_state}]. Guide the dialogue naturally toward the next phase.
"""

    def advance_state(self, current_state: str, user_text: str, turn_count: int) -> str:
        """
        State machine transition logic based on conversational cues and turn progression.
        """
        text_lower = user_text.lower()

        # Check for immediate terminal conditions
        if any(w in text_lower for w in ["human", "person", "representative", "agent", "transfer", "manager"]):
            return "HUMAN_HANDOFF"

        if any(w in text_lower for w in ["not interested", "stop calling", "remove me", "don't call", "no interest"]):
            return "CUSTOMER_NOT_INTERESTED"

        if any(w in text_lower for w in ["call later", "busy right now", "driving", "in a meeting"]):
            return "CALLBACK_REQUESTED"

        if any(w in text_lower for w in ["bye", "goodbye", "hang up", "thank you bye"]):
            return "CUSTOMER_HUNG_UP"

        # Check for objection handling cues
        if any(w in text_lower for w in ["expensive", "costly", "already have", "using another", "doubt", "trust", "why should i", "don't need"]):
            return "OBJECTION_HANDLING"

        # Check for buying intent
        if any(w in text_lower for w in ["sign up", "open account", "send link", "get started", "proceed", "sounds great", "pricing details"]):
            return "BUYING_INTENT"

        # Progression based on conversation flow
        if current_state == "INTRO":
            return "DISCOVERY"
        elif current_state == "DISCOVERY":
            return "PRODUCT_EXPLANATION"
        elif current_state == "PRODUCT_EXPLANATION":
            return "QUESTIONS"
        elif current_state == "QUESTIONS":
            return "BUYING_INTENT"
        elif current_state == "OBJECTION_HANDLING":
            return "BUYING_INTENT"
        elif current_state == "BUYING_INTENT":
            return "CLOSING"

        return current_state

    async def get_initial_greeting(self, customer: Dict[str, Any], product: Dict[str, Any]) -> str:
        """Generate the opening icebreaker when the call first connects."""
        cust_name = customer.get("name", "there")
        prod_name = product.get("name", "our product")
        return (
            f"Hi {cust_name}, I'm calling from {prod_name}. "
            f"Is this a good time for a quick two-minute introduction to our flexible savings plan?"
        )

    async def process_turn(
        self,
        customer: Dict[str, Any],
        product: Dict[str, Any],
        history: List[Dict[str, str]],
        current_state: str,
        user_utterance: str
    ) -> Dict[str, Any]:
        """
        Execute one conversational sales turn:
        1. Classify state transition
        2. Format prompt
        3. Invoke LLM provider
        4. Return response text, new state, and latency metrics
        """
        turn_count = len(history) // 2
        new_state = self.advance_state(current_state, user_utterance, turn_count)
        
        system_prompt = self.build_system_prompt(customer, product, new_state)
        
        # Prepare messages
        messages = list(history)
        messages.append({"role": "user", "content": user_utterance})

        llm_resp = await self.llm.generate_reply(messages, system_prompt)

        return {
            "reply_text": llm_resp.content,
            "new_state": new_state,
            "latency_ms": llm_resp.latency_ms,
            "is_terminal": new_state in TERMINAL_STATES
        }

    async def generate_post_call_analysis(
        self,
        transcript: List[Dict[str, Any]],
        product: Dict[str, Any],
        customer: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze full call transcript for post-call insights."""
        return await self.llm.analyze_call(
            transcript=transcript,
            product_name=product.get("name", "Product"),
            customer_name=customer.get("name", "Customer")
        )

conversation_service = ConversationService()

