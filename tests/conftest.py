"""
Pytest configuration for Ripple test suite.
Forces LLM_MODE=off for all tests except test_llm_mock.py to ensure
fast, deterministic, network-independent test runs regardless of .env settings.
"""
import pytest
import os
from config import settings

@pytest.fixture(autouse=True)
def force_deterministic_llm_mode(request, monkeypatch):
    if "test_llm_mock" not in str(request.node.fspath):
        monkeypatch.setenv("LLM_MODE", "off")
        monkeypatch.setattr(settings, "llm_mode", "off")
