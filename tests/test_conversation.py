import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.services.conversation_service import conversation_service

async def test_conversation_flow():
    customer = {
        "customer_id": "cust_test",
        "name": "Rahul Sharma",
        "company": "ABC Logistics",
        "designation": "Director",
        "notes": "Testing high returns"
    }
    product = {
        "product_id": "prod_smartsave",
        "name": "SmartSave+",
        "tagline": "Automated High-Yield Savings",
        "description": "SmartSave+ is an automated savings account with 8.5% interest.",
        "features": ["8.5% daily compounding interest", "Zero lock-in period"],
        "pricing": "Zero maintenance fees",
        "faqs": [{"q": "Is it safe?", "a": "Yes, RBI regulated."}],
        "objections": {"too_expensive": "There are zero maintenance charges."},
        "key_terms": ["SmartSave+", "NACH"]
    }

    # Test initial greeting
    greeting = await conversation_service.get_initial_greeting(customer, product)
    assert "Rahul" in greeting
    assert "SmartSave+" in greeting

    # Agent profile drives greeting and prompt
    agent = {
        "name": "Solar Agent",
        "persona_name": "Riya",
        "company_name": "SunVolt",
        "product_name": "SunVolt Rooftop Solar",
        "product_description": "Rooftop solar panels for homes.",
        "pricing": "Rs 60,000 per kW",
        "greeting": "Hello {customer_name}, {agent_name} from {company_name} here."
    }
    assert await conversation_service.get_initial_greeting(customer, agent) == "Hello Rahul Sharma, Riya from SunVolt here."
    prompt = conversation_service.build_system_prompt(customer, agent, "INTRO")
    assert "SunVolt Rooftop Solar" in prompt and "Rs 60,000 per kW" in prompt
    assert "SmartSave" not in prompt

    # Test objection handling state transition
    state1 = conversation_service.advance_state("DISCOVERY", "Your product sounds too expensive", 1)
    assert state1 == "OBJECTION_HANDLING"

    # Test buying intent transition
    state2 = conversation_service.advance_state("OBJECTION_HANDLING", "Okay, how do I open an account and sign up?", 2)
    assert state2 == "BUYING_INTENT"

    # Test terminal state transition (human handoff)
    state3 = conversation_service.advance_state("QUESTIONS", "Can I speak to a real human person?", 3)
    assert state3 == "HUMAN_HANDOFF"

    # Test post call analysis
    transcript = [
        {"role": "assistant", "text": "Hi Rahul, calling from SmartSave+."},
        {"role": "user", "text": "I am very interested, sign me up for the account!"}
    ]
    analysis = await conversation_service.generate_post_call_analysis(transcript, product, customer)
    assert analysis["outcome"] in ["interested", "converted"]
    assert analysis["buying_intent"] >= 0.8
    assert "summary" in analysis

    print("Conversation service tests passed successfully!")

if __name__ == "__main__":
    asyncio.run(test_conversation_flow())

