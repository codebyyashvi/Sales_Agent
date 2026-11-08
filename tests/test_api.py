import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from backend.app.main import app

def test_api_suite():
    with TestClient(app) as client:
        # 1. Health check
        res = client.get("/health")
        assert res.status_code == 200
        health = res.json()
        assert health["status"] == "healthy"
        assert health["twilio_configured"] is True
        assert health["gnani_configured"] is True
        print("✓ /health passed")

        # 2. Twilio TwiML endpoint
        res = client.post("/twilio/voice?call_id=test_call_123")
        assert res.status_code == 200
        assert "application/xml" in res.headers["content-type"]
        assert "<Connect>" in res.text
        assert "<Stream" in res.text
        assert "/ws/twilio-media" in res.text
        print("✓ /twilio/voice TwiML endpoint passed")

        # 3. List customers
        res = client.get("/api/customers")
        assert res.status_code == 200
        print(f"✓ /api/customers passed (retrieved {len(res.json())} leads)")

        # 4. List products
        res = client.get("/api/products")
        assert res.status_code == 200
        print(f"✓ /api/products passed (retrieved {len(res.json())} products)")

        # 5. Start browser call session
        payload = {
            "phone_number": "browser_test",
            "customer_id": "cust_rahul",
            "product_id": "prod_smartsave"
        }
        res = client.post("/api/calls/start", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "call_id" in data
        assert data["status"] == "initiated"
        call_id = data["call_id"]
        print(f"✓ /api/calls/start passed (session {call_id})")

        # 6. Retrieve call detail
        res = client.get(f"/api/calls/{call_id}")
        assert res.status_code == 200
        assert res.json()["call_id"] == call_id
        print("✓ /api/calls/{id} passed")

        # 7. End call
        res = client.post(f"/api/calls/{call_id}/end")
        assert res.status_code == 200
        print("✓ /api/calls/{id}/end passed")

        # 8. Sales agent CRUD + call session bound to that agent
        agent_payload = {
            "name": "Test Solar Agent",
            "persona_name": "Riya",
            "company_name": "SunVolt",
            "product_name": "SunVolt Rooftop Solar",
            "product_description": "Rooftop solar panels for homes.",
            "key_features": ["25 year warranty"],
            "pricing": "Rs 60,000 per kW",
            "faqs": [{"q": "Subsidy?", "a": "Yes, subsidy applies."}],
            "objections": [{"objection": "too costly", "response": "EMI starts at 2000 a month."}],
            "greeting": "Hello {customer_name}, {agent_name} here from {company_name}."
        }
        res = client.post("/api/agents", json=agent_payload)
        assert res.status_code == 200
        agent_id = res.json()["agent_id"]

        res = client.put(f"/api/agents/{agent_id}", json={**agent_payload, "pricing": "Rs 55,000 per kW"})
        assert res.status_code == 200
        assert res.json()["pricing"] == "Rs 55,000 per kW"

        res = client.post("/api/calls/start", json={
            "phone_number": "browser_agent_test",
            "agent_id": agent_id,
            "customer_name": "Amit"
        })
        assert res.status_code == 200
        agent_call_id = res.json()["call_id"]
        detail = client.get(f"/api/calls/{agent_call_id}").json()
        assert detail["agent_id"] == agent_id
        assert detail["product_name"] == "SunVolt Rooftop Solar"
        client.post(f"/api/calls/{agent_call_id}/end")

        assert client.post("/api/calls/start", json={"phone_number": "browser_x", "agent_id": "agent_missing"}).status_code == 404

        res = client.delete(f"/api/agents/{agent_id}")
        assert res.status_code == 200
        assert client.get(f"/api/agents/{agent_id}").status_code == 404
        print("✓ /api/agents CRUD + agent-bound call session passed")

        # 9. Analytics overview
        res = client.get("/api/analytics/overview")
        assert res.status_code == 200
        assert "total_calls" in res.json()
        print("✓ /api/analytics/overview passed")

    print("\n🎉 All FastAPI API integration tests passed successfully!")

if __name__ == "__main__":
    test_api_suite()

