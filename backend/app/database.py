import time
import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings

logger = logging.getLogger("sales_agent.database")

class Database:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

db_instance = Database()

async def connect_db():
    try:
        logger.info(f"Connecting to MongoDB at {settings.MONGO_URI.split('@')[-1] if '@' in settings.MONGO_URI else 'localhost'}...")
        db_instance.client = AsyncIOMotorClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000
        )
        # Verify connection
        await db_instance.client.admin.command('ping')
        db_instance.db = db_instance.client[settings.MONGO_DB_NAME]
        logger.info(f"MongoDB connected successfully to database: {settings.MONGO_DB_NAME}")
        await seed_initial_data()
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}. Running with degraded persistence mode.")
        db_instance.client = None
        db_instance.db = None

async def close_db():
    if db_instance.client:
        db_instance.client.close()
        logger.info("MongoDB connection closed.")

def get_db() -> Optional[AsyncIOMotorDatabase]:
    return db_instance.db

async def seed_initial_data():
    """Seed initial products, customers, and agent config if they don't exist yet."""
    db = db_instance.db
    if db is None:
        return

    # Seed Products
    existing_products = await db.products.count_documents({})
    if existing_products == 0:
        sample_products = [
            {
                "product_id": "prod_smartsave",
                "name": "SmartSave+",
                "tagline": "Automated High-Yield Savings with Instant Liquidity",
                "category": "Fintech / Wealth",
                "description": "SmartSave+ is an automated smart savings account offering 8.5% annual return with zero lock-in, automated NACH mandate deposits, and instant FlexiPay withdrawals.",
                "features": [
                    "8.5% annual interest calculated daily and paid monthly",
                    "Zero lock-in period with instant withdrawal anytime via UPI or RuPay card",
                    "Automated micro-investing from daily round-ups and monthly NACH mandate",
                    "FlexiPay emergency credit line up to 90% of accumulated savings balance"
                ],
                "pricing": "Zero maintenance fee. Free withdrawals up to 5 times a month. Annual plan includes free wealth advisory.",
                "faqs": [
                    {"q": "Is my money safe?", "a": "Yes, funds are held with RBI-regulated banking partners with ₹5 Lakh DICGC insurance coverage."},
                    {"q": "What is the minimum deposit?", "a": "You can start with as little as ₹500."},
                    {"q": "How do withdrawals work?", "a": "Instant 24x7 transfers to your linked bank account with no penalty."}
                ],
                "objections": {
                    "too_expensive": "There are no upfront or annual maintenance charges at all—you only earn interest on your deposits.",
                    "already_have_bank": "Unlike regular savings accounts that only offer 3% to 4%, SmartSave+ delivers up to 8.5% while keeping your money just as accessible.",
                    "trust_concern": "All client funds are safeguarded under RBI guidelines and insured up to ₹5 Lakhs by DICGC.",
                    "need_to_think": "I completely understand! We can set up a zero-commitment trial account with just ₹500 so you can experience the daily returns."
                },
                "key_terms": ["SmartSave+", "NACH", "FlexiPay", "RuPay", "DICGC", "RBI", "UPI", "8.5 percent"]
            },
            {
                "product_id": "prod_cloudshield",
                "name": "CloudShield AI",
                "tagline": "Real-time Autonomous Threat Defense for Cloud Workloads",
                "category": "Enterprise Security",
                "description": "CloudShield AI delivers zero-day exploit prevention, automated API vulnerability remediation, and continuous compliance monitoring for AWS, Azure, and GCP.",
                "features": [
                    "Autonomous sub-second threat isolation using neural behavioral models",
                    "One-click SOC2, ISO 27001, and HIPAA compliance readiness auditing",
                    "Automated infrastructure-as-code vulnerability scanning in CI/CD pipelines"
                ],
                "pricing": "Starting at $499/month for up to 50 cloud nodes with a 14-day full POC.",
                "faqs": [
                    {"q": "Does it impact server performance?", "a": "Agentless eBPF architecture with less than 0.2% CPU overhead."},
                    {"q": "How long is deployment?", "a": "Under 15 minutes with our Terraform or CloudFormation scripts."}
                ],
                "objections": {
                    "already_have_tool": "Most legacy tools generate noisy alerts without automated remediation. CloudShield AI takes proactive micro-isolation actions within 80 milliseconds.",
                    "budget": "Our clients typically save 40% on alert fatigue and incident response hours within the first month."
                },
                "key_terms": ["CloudShield", "eBPF", "Terraform", "SOC2", "zero-day", "micro-isolation"]
            }
        ]
        await db.products.insert_many(sample_products)
        logger.info(f"Seeded {len(sample_products)} sample products.")

    # Seed Customers
    existing_customers = await db.customers.count_documents({})
    if existing_customers == 0:
        sample_customers = [
            {
                "customer_id": "cust_rahul",
                "name": "Rahul Sharma",
                "phone": "+919876543210",
                "company": "Apex Logistics",
                "designation": "Operations Director",
                "city": "Mumbai",
                "preferred_product_id": "prod_smartsave",
                "notes": "Interested in automated treasury savings for surplus operational funds.",
                "status": "lead"
            },
            {
                "customer_id": "cust_priya",
                "name": "Priya Patel",
                "phone": "+919811223344",
                "company": "Zenith Retail",
                "designation": "Founder & CEO",
                "city": "Bengaluru",
                "preferred_product_id": "prod_smartsave",
                "notes": "Looking for better returns than traditional fixed deposits with high liquidity.",
                "status": "lead"
            },
            {
                "customer_id": "cust_vikram",
                "name": "Vikram Malhotra",
                "phone": "+18088004708",
                "company": "Malhotra Tech Ventures",
                "designation": "CTO",
                "city": "San Francisco / Pune",
                "preferred_product_id": "prod_cloudshield",
                "notes": "Evaluating cloud security automation for multi-tenant microservices.",
                "status": "lead"
            }
        ]
        await db.customers.insert_many(sample_customers)
        logger.info(f"Seeded {len(sample_customers)} sample customers.")

    # Seed one example sales agent so the dashboard has something to dial with
    existing_agents = await db.agents.count_documents({})
    if existing_agents == 0:
        now = time.time()
        await db.agents.insert_one({
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
            "offers": "",
            "target_audience": "Salaried professionals and small business owners looking for better returns than a regular savings account.",
            "faqs": [
                {"q": "Is my money safe?", "a": "Yes, funds are held with RBI-regulated banking partners with 5 Lakh rupees DICGC insurance coverage."},
                {"q": "What is the minimum deposit?", "a": "You can start with as little as 500 rupees."}
            ],
            "objections": [
                {"objection": "Too expensive", "response": "There are no upfront or annual maintenance charges at all, you only earn interest on your deposits."},
                {"objection": "I already have a bank account", "response": "Regular savings accounts offer 3 to 4 percent, SmartSave+ delivers up to 8.5 percent with the same instant access."}
            ],
            "call_objective": "Get the customer to open a zero-commitment trial account with 500 rupees.",
            "greeting": "Hi {customer_name}, this is {agent_name} calling from {company_name}. Is this a good time for a quick two-minute chat about earning more on your savings?",
            "closing_message": "Thank you so much for your time. Have a wonderful day!",
            "tone": "Warm, polite, professional and consultative",
            "additional_instructions": "",
            "language": "en-IN",
            "voice": "",
            "key_terms": ["SmartSave+", "NACH", "FlexiPay", "RuPay", "DICGC", "RBI", "UPI"],
            "created_at": now,
            "updated_at": now
        })
        logger.info("Seeded sample sales agent.")

