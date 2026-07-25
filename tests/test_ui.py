"""
Unit tests for V.E.G.A.S. Mission Control Web Interface static mounting and index serving.
"""

from fastapi.testclient import TestClient
import api


def test_index_html_served_on_root():
    client = TestClient(api.app)
    res = client.get("/")
    assert res.status_code == 200
    assert "V.E.G.A.S. AIOS — Mission Control HUD" in res.text
    assert "aiCoreCanvas" in res.text
    assert "SPECIALIST AGENTS" in res.text


def test_static_css_asset_served():
    client = TestClient(api.app)
    res = client.get("/static/aether.css")
    assert res.status_code == 200
    assert "Orbitron" in res.text or "--hud-cyan" in res.text


def test_static_ai_core_js_served():
    client = TestClient(api.app)
    res = client.get("/static/ai_core.js")
    assert res.status_code == 200
    assert "AICoreRenderer" in res.text or "drawCentralGlow" in res.text


def test_static_aether_js_served():
    client = TestClient(api.app)
    res = client.get("/static/aether.js")
    assert res.status_code == 200
    assert "fetchSystemStatus" in res.text
