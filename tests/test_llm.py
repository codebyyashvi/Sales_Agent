import sys, asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))
from app.services.providers.llm_provider import AzureOpenAIProvider

agent_smartsave = {
    "agent_id": "agent_smartsave",
    "name": "SmartSave+ Savings Agent",
    "description": "Example agent that pitches the SmartSave+ automated savings account.",
    "persona_name": "Aria",
    "company_name": "SmartSave+",
    "product_name": "SmartSave+",
    "product_description": "SmartSave+ is an automated smart savings account offering 8.5% annual return with zero lock-in, automated NACH mandate deposits, and instant FlexiPay withdrawals.",
    "key_features": [
        "8.5% annual interest calculated daily and paid monthly",
        "Zero lock-in period with instant withdrawal anytime via UPI or RuPay card",
        "Automated micro-investing from daily round-ups and monthly NACH mandate",
        "FlexiPay emergency credit line up to 90% of accumulated savings balance"
    ],
    "pricing": "Zero maintenance fee. Free withdrawals up to 5 times a month. Annual plan includes free wealth advisory.",
    "offers": "Get 100 rupees bonus on your first deposit.",
    "target_audience": "Salaried professionals and small business owners.",
    "faqs": [
        {
            "q": "Is my money safe?",
            "a": "Yes, funds are held with RBI-regulated banking partners with 5 Lakh rupees DICGC insurance coverage."
        },
        {
            "q": "What is the minimum deposit?",
            "a": "You can start with as little as 500 rupees."
        }
    ],
    "objections": [
        {
            "objection": "Too expensive",
            "response": "There are no upfront or annual maintenance charges at all, you only earn interest on your deposits."
        },
        {
            "objection": "I already have a bank account",
            "response": "Regular savings accounts offer 3 to 4 percent, SmartSave+ delivers up to 8.5 percent with the same instant access."
        }
    ],
    "call_objective": "Get the customer to open a zero-commitment trial account with 500 rupees.",
    "greeting": "Hi there, this is Aria calling from SmartSave+. Is this a good time for a quick two-minute chat about earning more on your savings?",
    "closing_message": "Thank you so much for your time. Have a wonderful day!"
}

async def test_turns():
    llm = AzureOpenAIProvider()
    test_queries = [
        "Hello, who is this and what is this call about?",
        "How does it work and what are the main features?",
        "What are your charges and pricing?",
        "Is my money safe with you?",
        "What is the minimum deposit to start?",
        "I already have a regular bank account, why do I need this?",
        "Sounds good, how can I sign up?",
        "No thanks, bye!"
    ]

    print("=== Testing Agent-Aware Conversational Turns ===")
    for q in test_queries:
        messages = [{"role": "user", "content": q}]
        res = await llm.generate_reply(messages, "System prompt for Aria", agent_profile=agent_smartsave)
        print(f"\nUser: {q}")
        print(f"Agent: {res.content}")
        print(f"Latency: {res.latency_ms:.1f}ms")

if __name__ == "__main__":
    asyncio.run(test_turns())
