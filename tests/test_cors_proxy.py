"""
Tests for split-hosting support:
- Strict CORS preflight behavior (allowed origin vs disallowed origin, never wildcard)
- Rate limiting behind trusted proxy vs ignored spoofed headers when TRUST_PROXY=0
"""
import os
import pytest
from fastapi.testclient import TestClient
from api import app, reset_rate_limits
from config import settings

@pytest.fixture
def client():
    return TestClient(app)

def test_cors_preflight_allowed_origin(client, monkeypatch):
    allowed_origin = "https://ripple-frontend.pages.dev"
    monkeypatch.setenv("CORS_ORIGINS", f"{allowed_origin},https://another-domain.com")

    headers = {
        "Origin": allowed_origin,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "content-type",
    }
    response = client.options("/api/tasks", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == allowed_origin
    assert response.headers.get("access-control-allow-credentials") is None or response.headers.get("access-control-allow-credentials") == "false"
    assert response.headers.get("access-control-allow-origin") != "*"

def test_cors_preflight_disallowed_origin(client, monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://trusted-site.com")
    headers = {
        "Origin": "https://malicious-attacker.com",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/api/tasks", headers=headers)
    assert response.status_code == 400
    assert response.headers.get("access-control-allow-origin") is None

def test_cors_default_empty_origins_blocks_cross_origin(client, monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "")
    headers = {
        "Origin": "https://any-external-domain.com",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/api/tasks", headers=headers)
    assert response.status_code == 400
    assert response.headers.get("access-control-allow-origin") is None

def test_rate_limiting_trusted_proxy_separate_budgets(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_MODE", "1")
    monkeypatch.setenv("TRUST_PROXY", "1")
    reset_rate_limits()

    client_a_ip = "198.51.100.22"
    client_b_ip = "203.0.113.88"

    # Client A consumes its 10 requests/min quota
    for i in range(10):
        resp = client.post(
            "/api/chat",
            json={"tenant": "cardio", "text": f"hello {i}"},
            headers={"X-Forwarded-For": client_a_ip}
        )
        assert resp.status_code == 200, f"Request {i+1} failed: {resp.text}"

    # Client A's 11th request is blocked with 429
    resp_blocked = client.post(
        "/api/chat",
        json={"tenant": "cardio", "text": "over limit"},
        headers={"X-Forwarded-For": client_a_ip}
    )
    assert resp_blocked.status_code == 429
    assert "Rate limit exceeded" in resp_blocked.json()["detail"]

    # Client B should still have full quota (separate budget)
    resp_b = client.post(
        "/api/chat",
        json={"tenant": "cardio", "text": "hello from b"},
        headers={"X-Forwarded-For": client_b_ip}
    )
    assert resp_b.status_code == 200

    # Also test multi-hop X-Forwarded-For where client B is last in chain
    multi_hop_ip = "192.0.2.1, 203.0.113.88"
    resp_multi = client.post(
        "/api/chat",
        json={"tenant": "cardio", "text": "multi hop b"},
        headers={"X-Forwarded-For": multi_hop_ip}
    )
    assert resp_multi.status_code == 200

def test_rate_limiting_spoofed_header_ignored_when_trust_proxy_zero(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_MODE", "1")
    monkeypatch.setenv("TRUST_PROXY", "0")
    reset_rate_limits()

    # Client sends 10 requests with arbitrary changing X-Forwarded-For headers
    for i in range(10):
        resp = client.post(
            "/api/chat",
            json={"tenant": "cardio", "text": f"spoofed request {i}"},
            headers={"X-Forwarded-For": f"198.51.100.{i+1}"}
        )
        assert resp.status_code == 200, f"Request {i+1} failed: {resp.text}"

    # 11th request tries to spoof another new IP
    resp_spoofed_11 = client.post(
        "/api/chat",
        json={"tenant": "cardio", "text": "trying to bypass with new spoofed IP"},
        headers={"X-Forwarded-For": "198.51.100.99"}
    )
    # Because TRUST_PROXY=0, the header is ignored and socket IP was tracked; 11th request is 429!
    assert resp_spoofed_11.status_code == 429
    assert "Rate limit exceeded" in resp_spoofed_11.json()["detail"]
