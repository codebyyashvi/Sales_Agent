import os
import re
import time
import json
import logging
import httpx
from typing import List, Dict, Any, Optional
from openai import AsyncAzureOpenAI, AsyncOpenAI
try:
    from groq import AsyncGroq
except ImportError:
    AsyncGroq = None

from app.config import settings
from app.services.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger("sales_agent.llm")


class AgentAwareSalesEngine:
    """
    Intelligent Sales Dialogue Engine that responds using the EXACT profile,
    description, features, pricing, FAQs, and objection handling of the selected agent.
    Acts as an immediate zero-downtime, sub-millisecond fallback when external LLM endpoints are unreachable.
    """

    @classmethod
    def extract_agent_context(
        cls,
        agent_profile: Optional[Dict[str, Any]],
        system_prompt: str
    ) -> Dict[str, Any]:
        profile = dict(agent_profile or {})

        # Extract missing fields from system_prompt if not directly in agent_profile
        if not profile.get("product_name") and "selling " in system_prompt:
            m = re.search(r"calling on behalf of (.+?) to sell (.+?)\.", system_prompt)
            if m:
                profile.setdefault("company_name", m.group(1).strip())
                profile.setdefault("product_name", m.group(2).strip())

        persona = profile.get("persona_name") or profile.get("name") or "Aria"
        company = profile.get("company_name") or profile.get("product_name") or "our company"
        product = profile.get("product_name") or "our product"
        description = (
            profile.get("product_description")
            or profile.get("description")
            or f"{product} is our premier solution from {company}."
        )
        features = profile.get("key_features") or []
        pricing = profile.get("pricing") or ""
        offers = profile.get("offers") or ""
        faqs = profile.get("faqs") or []
        objections = profile.get("objections") or []
        call_objective = profile.get("call_objective") or f"Help you discover how {product} can benefit you."
        closing = profile.get("closing_message") or "Thank you so much for your time today. Have a wonderful day ahead, goodbye!"

        return {
            "persona": persona,
            "company": company,
            "product": product,
            "description": description,
            "features": features,
            "pricing": pricing,
            "offers": offers,
            "faqs": faqs,
            "objections": objections,
            "call_objective": call_objective,
            "closing": closing,
        }

    @classmethod
    def generate_reply(
        cls,
        messages: List[Dict[str, str]],
        system_prompt: str,
        agent_profile: Optional[Dict[str, Any]] = None
    ) -> str:
        ctx = cls.extract_agent_context(agent_profile, system_prompt)
        product = ctx["product"]
        company = ctx["company"]
        persona = ctx["persona"]
        description = ctx["description"]
        features = ctx["features"]
        pricing = ctx["pricing"]
        offers = ctx["offers"]
        faqs = ctx["faqs"]
        objections = ctx["objections"]
        call_objective = ctx["call_objective"]
        closing = ctx["closing"]

        # Count user turns
        user_messages = [m for m in messages if m.get("role") == "user"]
        user_turn_count = len(user_messages)

        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "").lower().strip()
                break

        prev_assistant_msg = ""
        for m in reversed(messages):
            if m.get("role") == "assistant":
                prev_assistant_msg = m.get("content", "").lower().strip()
                break

        raw_tokens = set(re.findall(r"\w+", last_user_msg))
        stop_words = {
            "what", "is", "the", "a", "an", "to", "for", "in", "on", "at", "of", "with",
            "and", "or", "do", "does", "did", "you", "i", "we", "they", "he", "she", "it",
            "my", "your", "our", "their", "this", "that", "these", "those", "can", "could",
            "would", "should", "are", "am", "be", "been", "being", "have", "has", "had",
            "how", "why", "who", "which", "where", "when", "tell", "me", "about"
        }
        content_tokens = raw_tokens - stop_words

        # 1. Terminal / Exit intents
        if any(w in last_user_msg for w in ["bye", "goodbye", "hang up", "talk later", "no thanks", "not interested", "stop calling"]):
            return closing

        # 2. Human escalation
        if any(w in last_user_msg for w in ["human", "real person", "representative", "manager", "transfer", "supervisor"]):
            return f"Of course! I will arrange for a senior representative from {company} to connect with you shortly."

        # 3. Busy / Callback
        if any(w in last_user_msg for w in ["busy", "call later", "not right now", "driving", "meeting", "call me back"]):
            return f"I completely understand. When would be a more convenient time to reach you regarding {product}?"

        # 4. Identity / Greeting / "Who is this?"
        if any(w in last_user_msg for w in ["who is this", "who are you", "what company", "who am i speaking", "why are you calling"]):
            return f"Hi! I'm {persona} calling from {company}. We help customers with {product} — {description[:120]}... Do you have a quick moment?"

        # 5. Confirmation to send details/link (if assistant previously offered to send link or details)
        if any(w in prev_assistant_msg for w in ["send the details", "send details", "share the signup link", "share details", "send the link", "to your number", "shall i proceed"]):
            if any(w in last_user_msg for w in ["yes", "sure", "yeah", "okay", "ok", "please", "send", "proceed", "do that", "alright"]):
                return f"Perfect! I've sent the details and link directly to your mobile number via SMS. {closing}"

        # 6. Turn 1 Affirmative Response to Greeting ("Yes, I have time" / "Sure" / "Go ahead")
        # Pitch product overview and top feature from the agent's profile, then ask if they'd like to hear about pricing or how it works.
        if user_turn_count <= 1 and any(w in last_user_msg for w in ["yes", "sure", "yeah", "yep", "ok", "okay", "go ahead", "tell me", "listening", "fine", "what is it", "tell me more"]):
            feature_sample = f" One of our biggest highlights is that {features[0]}." if features else ""
            return f"Wonderful! {description}{feature_sample} Would you like to hear about our pricing and returns, or how the account works?"

        # 7. Pricing & Cost Queries
        if any(w in last_user_msg for w in ["price", "pricing", "cost", "charges", "fees", "fee", "rate", "interest", "returns"]):
            if pricing:
                offer_txt = f" Plus, we currently have: {offers}." if offers else ""
                return f"With {product}, {pricing}.{offer_txt} Would you like me to help you get started?"
            elif features:
                return f"With {product}, you get {features[0]}. There are no hidden fees. Shall I share more details?"

        # 8. FAQs Matching (Score by content keyword overlap)
        best_faq = None
        best_faq_score = 0
        for faq in faqs:
            q_text = faq.get("q", "").lower()
            q_content_tokens = set(re.findall(r"\w+", q_text)) - stop_words
            overlap = len(content_tokens.intersection(q_content_tokens))
            for kw in ["safe", "safety", "secure", "security", "minimum", "deposit", "rbi", "dicgc", "licence", "guarantee"]:
                if kw in content_tokens and kw in q_content_tokens:
                    overlap += 3
            if overlap > best_faq_score and overlap >= 1:
                best_faq_score = overlap
                best_faq = faq

        if best_faq and best_faq.get("a"):
            ans = best_faq["a"].strip()
            return f"{ans} Would you like to know more about how {product} works, or see how to get started?"

        # 9. Objections Handling (Match against approved rebuttals)
        best_obj = None
        best_obj_score = 0
        for obj in objections:
            obj_text = obj.get("objection", "").lower()
            obj_content_tokens = set(re.findall(r"\w+", obj_text)) - stop_words
            overlap = len(content_tokens.intersection(obj_content_tokens))
            for kw in ["expensive", "costly", "already", "bank", "account", "competitor", "trust"]:
                if kw in content_tokens and kw in obj_content_tokens:
                    overlap += 3
            if overlap > best_obj_score and overlap >= 1:
                best_obj_score = overlap
                best_obj = obj

        if best_obj and best_obj.get("response"):
            resp = best_obj["response"].strip()
            return f"{resp} Does that address your concern?"

        # 10. Product Overview / Features / "How does it work?"
        if any(w in last_user_msg for w in ["what is", "tell me more", "how does it work", "features", "details", "explain", "benefit", "what do you do", "main features"]):
            feature_sample = f" Key highlights include {features[0]}." if features else ""
            return f"{description}{feature_sample} Would you like to hear about our key benefits or pricing?"

        # 11. Buying Intent / Agreement / "Sign up" / "Open account"
        if any(w in last_user_msg for w in ["sign up", "open account", "proceed", "send link", "lets do it", "how to join", "join", "get started", "sounds good", "interested", "yes", "sure", "okay"]):
            if call_objective:
                obj_clean = call_objective.strip().rstrip(".")
                if obj_clean.lower().startswith("get the customer to "):
                    obj_clean = "We can " + obj_clean[20:]
                return f"Wonderful! {obj_clean}. Would you like me to send the details directly to your number?"
            return f"Wonderful! I can share the signup link for {product} with you right away. Shall I proceed?"

        # 12. Greeting / Identity Check / "Who is this?"
        if any(w in last_user_msg for w in ["who is this", "who are you", "what company", "hello", "hi"]):
            return f"Hi! I'm {persona} calling from {company}. We help customers with {product} — {description[:120]}... Do you have a quick moment?"

        # 13. Contextual Fallback incorporating agent knowledge
        if features:
            f_txt = features[0]
            return f"With {product}, one of the biggest advantages is that you get {f_txt}. How does that align with what you're looking for?"

        return f"With {product}, our goal is to {call_objective.lower() if call_objective else 'give you the best value'}. What questions can I answer for you about {product}?"


class AzureOpenAIProvider(LLMProvider):
    """
    Multi-Provider Voice LLM Service supporting:
    1. Groq (llama-3.1-8b-instant) — Ultra-fast inference (<300ms) matching Node.js reference
    2. Standard OpenAI (gpt-4o-mini)
    3. Azure OpenAI (gpt-4o-mini)
    4. Intelligent Agent-Aware Sales Engine Fallback (Zero downtime, fully aligned with selected agent)
    """

    def __init__(self):
        # Groq client
        self.groq_api_key = (settings.GROQ_API_KEY or os.environ.get("GROQ_API_KEY", "")).strip()
        self.groq_model = settings.GROQ_MODEL or "llama-3.1-8b-instant"
        self.groq_client: Optional[Any] = None
        if self.groq_api_key and AsyncGroq:
            try:
                self.groq_client = AsyncGroq(api_key=self.groq_api_key)
                logger.info(f"Groq client initialized for model: {self.groq_model}")
            except Exception as e:
                logger.warning(f"Could not initialize Groq client: {e}")

        # OpenAI client
        self.openai_api_key = (settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY", "")).strip()
        self.openai_client: Optional[AsyncOpenAI] = None
        if self.openai_api_key:
            try:
                self.openai_client = AsyncOpenAI(api_key=self.openai_api_key, timeout=8.0)
                logger.info(f"OpenAI client initialized for model: {settings.OPENAI_MODEL}")
            except Exception as e:
                logger.warning(f"Could not initialize AsyncOpenAI: {e}")

        # Azure OpenAI client
        self.endpoint = settings.OPEN_AI_ENDPOINT.rstrip("/") if settings.OPEN_AI_ENDPOINT else ""
        self.azure_key = settings.OPEN_AI_KEY
        self.deployment = settings.OPEN_AI_DEPLOYMENT_NAME
        self.api_version = settings.OPEN_AI_API_VERSION
        self.azure_client: Optional[AsyncAzureOpenAI] = None
        if self.endpoint and self.azure_key:
            try:
                self.azure_client = AsyncAzureOpenAI(
                    azure_endpoint=self.endpoint,
                    api_key=self.azure_key,
                    api_version=self.api_version,
                    timeout=8.0
                )
                logger.info(f"Azure OpenAI client initialized for endpoint: {self.endpoint}")
            except Exception as e:
                logger.warning(f"Could not initialize AsyncAzureOpenAI: {e}")

    async def generate_reply(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        temperature: float = 0.2,
        agent_profile: Optional[Dict[str, Any]] = None
    ) -> LLMResponse:
        start_time = time.perf_counter()
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        # 1. Attempt Groq (Ultra-fast voice LLM, matches Node.js workflowCall.js)
        if self.groq_client:
            try:
                chat_completion = await self.groq_client.chat.completions.create(
                    model=self.groq_model,
                    temperature=temperature,
                    max_tokens=150,
                    messages=full_messages
                )
                reply = chat_completion.choices[0].message.content.strip()
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.info(f"[Groq LLM] Generated reply in {latency_ms:.1f}ms: '{reply}'")
                return LLMResponse(content=reply, latency_ms=round(latency_ms, 2))
            except Exception as e:
                logger.warning(f"[Groq LLM] Request failed: {e}. Trying next provider...")

        # 2. Attempt OpenAI
        if self.openai_client:
            try:
                resp = await self.openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=full_messages,
                    max_tokens=120,
                    temperature=temperature
                )
                reply = resp.choices[0].message.content.strip()
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.info(f"[OpenAI] Generated reply in {latency_ms:.1f}ms: '{reply}'")
                return LLMResponse(content=reply, latency_ms=round(latency_ms, 2))
            except Exception as e:
                logger.warning(f"[OpenAI] Request failed: {e}. Trying next provider...")

        # 3. Attempt Azure OpenAI REST API
        if self.endpoint and self.azure_key and "gapgpt" not in self.endpoint:
            url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}"
            headers = {
                "api-key": self.azure_key,
                "Content-Type": "application/json"
            }
            body = {
                "messages": full_messages,
                "max_tokens": 120,
                "temperature": temperature
            }
            try:
                async with httpx.AsyncClient(timeout=6.0) as client:
                    resp = await client.post(url, json=body, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        reply = data["choices"][0]["message"]["content"].strip()
                        latency_ms = (time.perf_counter() - start_time) * 1000
                        logger.info(f"[Azure OpenAI] Generated reply in {latency_ms:.1f}ms: '{reply}'")
                        return LLMResponse(content=reply, latency_ms=round(latency_ms, 2))
            except Exception as e:
                logger.warning(f"[Azure OpenAI] Request failed: {e}")

        # 4. Intelligent Agent-Aware Sales Engine Fallback
        # Dynamically uses the selected agent's description, features, pricing, FAQs, and objections
        logger.info("[LLM] Executing Intelligent Agent-Aware Sales Engine")
        reply = AgentAwareSalesEngine.generate_reply(messages, system_prompt, agent_profile=agent_profile)
        latency_ms = (time.perf_counter() - start_time) * 1000
        return LLMResponse(content=reply, latency_ms=round(latency_ms, 2))

    async def analyze_call(
        self,
        transcript: List[Dict[str, Any]],
        product_name: str,
        customer_name: str
    ) -> Dict[str, Any]:
        """
        Produce structured JSON post-call summary, sentiment, objections, and buying intent score.
        Uses Groq/OpenAI if available, with heuristic fallback.
        """
        full_text = " ".join([f"{t.get('role', '')}: {t.get('text', '')}" for t in transcript]).lower()

        # Try Groq or OpenAI for AI-powered analysis
        analysis_client = self.groq_client or self.openai_client
        model = self.groq_model if self.groq_client else settings.OPENAI_MODEL
        if analysis_client and transcript:
            prompt = (
                f"You are a sales call analyst. Analyze this call transcript between a sales agent selling '{product_name}' "
                f"and customer '{customer_name}':\n\n"
                f"{json.dumps(transcript, indent=2)}\n\n"
                "Return ONLY a valid JSON object with the following keys:\n"
                "- outcome: one of ['converted', 'interested', 'callback_requested', 'not_interested', 'human_handoff']\n"
                "- buying_intent: float between 0.0 and 1.0\n"
                "- sentiment: one of ['positive', 'neutral', 'negative']\n"
                "- objections: list of strings (objections raised by customer)\n"
                "- summary: 2-sentence summary of the conversation\n"
                "- recommended_action: 1 sentence next action for the sales team\n"
                "- follow_up_required: boolean"
            )
            try:
                resp = await analysis_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=250
                )
                raw = resp.choices[0].message.content.strip()
                # Clean code blocks if present
                if "```json" in raw:
                    raw = raw.split("```json")[1].split("```")[0].strip()
                elif "```" in raw:
                    raw = raw.split("```")[1].split("```")[0].strip()
                data = json.loads(raw)
                return data
            except Exception as e:
                logger.warning(f"AI call analysis failed: {e}. Using heuristic analyzer.")

        # Heuristic Analysis Fallback
        buying_intent = 0.5
        outcome = "callback_requested"
        sentiment = "neutral"
        objections = []

        if any(w in full_text for w in ["expensive", "costly", "high price"]):
            objections.append("PRICE")
        if any(w in full_text for w in ["already have", "using bank", "competitor"]):
            objections.append("ALREADY_HAVE_PRODUCT")
        if any(w in full_text for w in ["not interested", "no thanks", "don't want"]):
            objections.append("NOT_INTERESTED")
            outcome = "not_interested"
            sentiment = "negative"
            buying_intent = 0.15

        if any(w in full_text for w in ["human", "representative", "transfer"]):
            outcome = "human_handoff"
            buying_intent = 0.75

        if any(w in full_text for w in ["yes", "interested", "send link", "sign up", "open account", "sounds good"]):
            outcome = "interested"
            sentiment = "positive"
            buying_intent = 0.85

        if any(w in full_text for w in ["done", "sign me up", "let's do it"]):
            outcome = "converted"
            sentiment = "positive"
            buying_intent = 0.95

        summary = f"Spoke with {customer_name} regarding {product_name}. Customer discussed feature highlights and flexibility. Outcome identified as {outcome.replace('_', ' ').title()}."
        rec_action = "Follow up with WhatsApp summary and schedule a product demo call within 24 hours."

        return {
            "outcome": outcome,
            "buying_intent": round(buying_intent, 2),
            "sentiment": sentiment,
            "objections": objections if objections else ["NONE_EXPRESSED"],
            "summary": summary,
            "recommended_action": rec_action,
            "follow_up_required": outcome in ["interested", "callback_requested", "human_handoff"]
        }
