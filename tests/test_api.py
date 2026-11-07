import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app

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

        # 8. Analytics overview
        res = client.get("/api/analytics/overview")
        assert res.status_code == 200
        assert "total_calls" in res.json()
        print("✓ /api/analytics/overview passed")

    print("\n🎉 All FastAPI API integration tests passed successfully!")

if __name__ == "__main__":
    test_api_suite()

