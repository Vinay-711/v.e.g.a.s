"""
Unit tests for V.E.G.A.S. Final Polish enhancements.

Tests:
  - Desktop security headers (X-Frame-Options, X-Content-Type-Options)
  - System status endpoint metrics
  - Web UI asset accessibility
"""

from fastapi.testclient import TestClient
import api


def test_security_headers_present_on_response():
    client = TestClient(api.app)
    res = client.get("/")
    assert res.status_code == 200
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("X-Content-Type-Options") == "nosniff"


def test_system_status_endpoint_metrics():
    client = TestClient(api.app)
    res = client.get("/api/system-status")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "agents" in data
    assert "companion" in data
    assert "planner" in data
    assert "brain" in data


def test_web_assets_accessibility():
    client = TestClient(api.app)
    for asset in ["/static/aether.css", "/static/ai_core.js", "/static/aether.js", "/static/voice.js"]:
        res = client.get(asset)
        assert res.status_code == 200, f"Asset {asset} failed to load"
