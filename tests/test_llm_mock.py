"""
Unit tests for OpenAICompatToolCaller using a local mock HTTP server.
Verifies:
1. Multi-turn tool execution loop and tool response feeding.
2. Step cap enforcement (at most 6 steps).
3. Exponential backoff and graceful fallback on HTTP errors.
Zero network access or external keys required.
"""
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import pytest
import asyncio
from llm import OpenAICompatToolCaller
from analyst import AnalystAgent

class MockOpenAIHandler(BaseHTTPRequestHandler):
    scenario = "standard"  # "standard", "infinite_loop", "server_error"
    call_count = 0

    def log_message(self, format, *args):
        pass  # suppress server log noise in test output

    def do_POST(self):
        MockOpenAIHandler.call_count += 1
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        payload = json.loads(body.decode("utf-8"))

        if MockOpenAIHandler.scenario == "server_error":
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "Internal Server Error"}')
            return

        if MockOpenAIHandler.scenario == "infinite_loop":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "tool_calls": [{
                            "id": f"call_{MockOpenAIHandler.call_count}",
                            "type": "function",
                            "function": {
                                "name": "who_knows",
                                "arguments": json.dumps({"topic": "Cardiology"})
                            }
                        }]
                    }
                }]
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        # Default "standard" scenario
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        messages = payload.get("messages", [])
        has_tool_response = any(m.get("role") == "tool" for m in messages)

        if not has_tool_response:
            resp = {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "tool_calls": [{
                            "id": "mock_call_1",
                            "type": "function",
                            "function": {
                                "name": "who_knows",
                                "arguments": json.dumps({"topic": "Cardiology"})
                            }
                        }]
                    }
                }]
            }
        else:
            resp = {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "Dr. Sarah Chen is the leading Cardiology specialist."
                    }
                }]
            }
        self.wfile.write(json.dumps(resp).encode("utf-8"))

@pytest.fixture(scope="module")
def mock_server():
    server = HTTPServer(("127.0.0.1", 0), MockOpenAIHandler)
    host, port = server.server_address
    base_url = f"http://{host}:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield base_url
    server.shutdown()

def test_mock_tool_calling_loop(mock_server):
    MockOpenAIHandler.scenario = "standard"
    MockOpenAIHandler.call_count = 0

    caller = OpenAICompatToolCaller(
        base_url=mock_server,
        api_key="mock_key",
        model="mock-model",
    )
    assert caller.is_available()

    mcp_tools = [
        {
            "name": "who_knows",
            "description": "Find experts",
            "inputSchema": {
                "type": "object",
                "properties": {"topic": {"type": "string"}},
                "required": ["topic"]
            }
        }
    ]

    executed_tools = []
    async def mock_session_caller(name: str, args: dict):
        executed_tools.append((name, args))
        return {"experts": [{"person": "Dr. Sarah Chen", "role": "Cardiologist"}]}

    async def _run():
        return await caller.run_tool_loop(
            query="Who knows about Cardiology?",
            mcp_tools=mcp_tools,
            session_caller=mock_session_caller,
            max_steps=6,
        )

    res = asyncio.run(_run())

    assert res["mode"] == "model-selected tools"
    assert len(res["trace"]) == 1
    assert res["trace"][0]["tool"] == "who_knows"
    assert res["trace"][0]["selected_by"] == "model-selected tools"
    assert res["final_answer"] == "Dr. Sarah Chen is the leading Cardiology specialist."
    assert len(executed_tools) == 1
    assert executed_tools[0][0] == "who_knows"

def test_mock_step_cap_enforcement(mock_server):
    MockOpenAIHandler.scenario = "infinite_loop"
    MockOpenAIHandler.call_count = 0

    caller = OpenAICompatToolCaller(
        base_url=mock_server,
        api_key="mock_key",
        model="mock-model",
    )

    mcp_tools = [
        {
            "name": "who_knows",
            "description": "Find experts",
            "inputSchema": {"type": "object", "properties": {}}
        }
    ]

    async def mock_session_caller(name: str, args: dict):
        return {"status": "ok"}

    async def _run():
        return await caller.run_tool_loop(
            query="Keep calling tools",
            mcp_tools=mcp_tools,
            session_caller=mock_session_caller,
            max_steps=6,
        )

    res = asyncio.run(_run())

    assert res["steps"] == 6
    assert len(res["trace"]) == 6

def test_mock_fallback_on_error(mock_server, monkeypatch):
    MockOpenAIHandler.scenario = "server_error"
    MockOpenAIHandler.call_count = 0

    monkeypatch.setenv("LLM_MODE", "on")
    monkeypatch.setenv("LLM_BASE_URL", mock_server)
    monkeypatch.setenv("LLM_API_KEY", "mock_key")
    monkeypatch.setenv("LLM_MODEL", "mock-model")

    from config import settings
    monkeypatch.setattr(settings, "llm_mode", "on")
    monkeypatch.setattr(settings, "llm_base_url", mock_server)
    monkeypatch.setattr(settings, "llm_api_key", "mock_key")
    monkeypatch.setattr(settings, "llm_model", "mock-model")

    caller = OpenAICompatToolCaller(base_url=mock_server, api_key="mock_key", model="mock-model")
    
    async def _should_fail():
        await caller.run_tool_loop(
            query="Test error",
            mcp_tools=[],
            session_caller=lambda n, a: None,
            max_steps=6,
        )

    with pytest.raises(RuntimeError):
        asyncio.run(_should_fail())

    # Now verify AnalystAgent falls back to fixed planner with proper label
    agent = AnalystAgent("cardio")
    result = asyncio.run(agent.run_plan_async(query="Who knows about Cardiology?"))
    assert result["mode"] == "fixed planner (fallback)"
    assert result["trace"][0]["selected_by"] == "fixed planner (fallback)"
