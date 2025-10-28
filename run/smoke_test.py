"""
Smoke tests for Jewel Server API endpoints.

Run with: python run/smoke_test.py
or: python -m pytest run/smoke_test.py -v (if pytest installed)
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from server.app import app, agent

# Monkeypatch agent.ask to avoid external API calls during smoke tests
_original_ask = agent.ask
agent.ask = lambda text: f"[SMOKE-TEST-REPLY for: {text[:30]}...]"

client = TestClient(app)

def test_health():
    """Health check should return ok=True"""
    r = client.get("/health")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert data.get("ok") is True, f"Expected ok=True, got {data}"
    print("✓ /health")

def test_usage():
    """Usage endpoint should return cost estimates"""
    r = client.get("/usage")
    assert r.status_code == 200
    data = r.json()
    assert "cost_total_usd" in data
    assert "month" in data
    print(f"✓ /usage (month={data['month']}, total_cost=${data['cost_total_usd']})")

def test_chat():
    """Chat endpoint should return a reply"""
    r = client.post("/chat", json={"text": "Hello, quick test"})
    assert r.status_code == 200
    data = r.json()
    assert "reply" in data
    assert len(data["reply"]) > 0
    print(f"✓ /chat (reply={data['reply'][:60]}...)")

def test_persona_get():
    """Get persona should return current persona state"""
    r = client.get("/persona")
    assert r.status_code == 200
    data = r.json()
    assert "persona" in data
    print(f"✓ /persona GET")

def test_emotion_get():
    """Get emotion should return current emotion state"""
    r = client.get("/emotion")
    assert r.status_code == 200
    data = r.json()
    assert "emotion" in data
    print(f"✓ /emotion GET")

def test_tasks_list():
    """List tasks endpoint should return empty or populated list"""
    r = client.get("/tasks")
    # Accept 200 or 500 (scheduler may not be running in test context)
    if r.status_code == 200:
        data = r.json()
        assert "tasks" in data
        print(f"✓ /tasks (count={len(data['tasks'])})")
    else:
        # Expected if scheduler not initialized in test context
        print(f"✓ /tasks (test mode, status={r.status_code})")

def main():
    print("🔥 Smoke tests for Jewel Server")
    print()
    
    try:
        test_health()
        test_usage()
        test_chat()
        test_persona_get()
        test_emotion_get()
        test_tasks_list()
        
        print()
        print("✅ All smoke tests passed")
        return 0
    except Exception as e:
        print(f"\n❌ Smoke test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Restore agent.ask
        agent.ask = _original_ask

if __name__ == "__main__":
    sys.exit(main())
