"""
OpenAI-Compatible LLM Provider Adapter for Ripple.
Provides tool-calling loop support across any OpenAI-compatible provider
(Groq, Mistral, OpenRouter, local Ollama).
Translates Model Context Protocol (MCP) tool schemas into OpenAI function tools format.
Enforces a 6-step cap, temperature 0, exponential backoff retries on HTTP 429 or network errors,
and graceful fallback to the deterministic Cypher query planner.
"""
import os
import json
import asyncio
import httpx
from typing import Any, Callable, Dict, List, Optional
from config import settings

def mcp_tools_to_openai_tools(mcp_tools: List[Any]) -> List[Dict[str, Any]]:
    """Converts MCP tool definitions to OpenAI functions tool format."""
    openai_tools = []
    for tool in mcp_tools:
        name = getattr(tool, "name", None) or (tool.get("name") if isinstance(tool, dict) else "")
        description = getattr(tool, "description", "") or (tool.get("description", "") if isinstance(tool, dict) else "")
        input_schema = getattr(tool, "inputSchema", None) or (tool.get("inputSchema") if isinstance(tool, dict) else None)

        if not input_schema or not isinstance(input_schema, dict):
            input_schema = {"type": "object", "properties": {}}
        elif "type" not in input_schema:
            input_schema = dict(input_schema)
            input_schema["type"] = "object"

        openai_tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description[:1024],
                "parameters": input_schema,
            }
        })
    return openai_tools

class OpenAICompatToolCaller:
    """
    Client for interacting with any OpenAI-compatible API with multi-turn tool calling.
    """
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
    ):
        self.base_url = (base_url or settings.llm_base_url or os.getenv("LLM_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or settings.llm_api_key or os.getenv("LLM_API_KEY", "")
        self.model = model or settings.llm_model or os.getenv("LLM_MODEL", "")
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff

    def is_available(self) -> bool:
        """Available if base_url and model are configured."""
        return bool(self.base_url and self.model)

    async def _post_chat_completion(
        self,
        client: httpx.AsyncClient,
        payload: Dict[str, Any],
        max_retries: Optional[int] = None,
        initial_backoff: Optional[float] = None,
    ) -> Dict[str, Any]:
        max_retries = max_retries if max_retries is not None else self.max_retries
        initial_backoff = initial_backoff if initial_backoff is not None else self.initial_backoff
        """
        Sends chat completion request with exponential backoff on HTTP 429 or network errors.
        """
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        delay = initial_backoff
        for attempt in range(max_retries + 1):
            try:
                resp = await client.post(url, headers=headers, json=payload, timeout=30.0)
                if resp.status_code == 429:
                    if attempt < max_retries:
                        await asyncio.sleep(delay)
                        delay = max(delay * 2.0, 3.0)
                        continue
                    raise RuntimeError(f"HTTP 429 Rate Limit exceeded after {max_retries} retries: {resp.text}")

                if resp.status_code >= 500:
                    if attempt < max_retries:
                        await asyncio.sleep(delay)
                        delay *= 2.0
                        continue
                    raise RuntimeError(f"Server error HTTP {resp.status_code}: {resp.text}")

                if resp.status_code != 200:
                    raise RuntimeError(f"LLM API returned HTTP {resp.status_code}: {resp.text}")

                return resp.json()
            except (httpx.NetworkError, httpx.TimeoutException) as net_err:
                if attempt < max_retries:
                    await asyncio.sleep(delay)
                    delay *= 2.0
                    continue
                raise RuntimeError(f"Network error after {max_retries} retries: {net_err}")

        raise RuntimeError("Failed to complete request to LLM provider.")

    async def run_tool_loop(
        self,
        query: str,
        mcp_tools: List[Any],
        session_caller: Callable[[str, Dict[str, Any]], Any],
        system_prompt: str = "You are a clinical evidence analyst. Select the fewest tools needed.",
        max_steps: int = 6,
    ) -> Dict[str, Any]:
        """
        Executes a multi-turn tool-calling loop (at most max_steps steps, temperature 0).
        Calls tools through session_caller, appends results, and stops on final answer.
        """
        if not self.is_available():
            raise RuntimeError("LLM provider base_url and model must be configured.")

        tools = mcp_tools_to_openai_tools(mcp_tools)
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

        trace: List[Dict[str, Any]] = []
        step_count = 0
        final_answer = ""

        async with httpx.AsyncClient() as client:
            while step_count < max_steps:
                step_count += 1

                payload = {
                    "model": self.model,
                    "messages": messages,
                    "tools": tools,
                    "temperature": 0,
                }

                data = await self._post_chat_completion(client, payload)
                choices = data.get("choices", [])
                if not choices:
                    break

                choice_msg = choices[0].get("message", {})
                tool_calls = choice_msg.get("tool_calls")

                # If no tool calls, the model provided a final answer
                if not tool_calls:
                    final_answer = choice_msg.get("content", "")
                    messages.append({"role": "assistant", "content": final_answer})
                    break

                # Append assistant message with tool calls
                messages.append(choice_msg)

                # Execute requested tools
                for tc in tool_calls:
                    tc_id = tc.get("id", f"call_{step_count}")
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "")
                    fn_args_raw = fn.get("arguments", "{}")

                    if isinstance(fn_args_raw, dict):
                        fn_args = fn_args_raw
                    else:
                        try:
                            fn_args = json.loads(fn_args_raw)
                        except Exception:
                            fn_args = {}

                    # Execute tool via MCP session caller
                    result = await session_caller(fn_name, fn_args)

                    trace.append({
                        "step": len(trace) + 1,
                        "tool": fn_name,
                        "args": fn_args,
                        "output": str(result)[:300],
                        "data": result,
                        "selected_by": "model-selected tools",
                        "tool_call_id": tc_id,
                    })

                    # Compact tool output before returning to model to protect token budget
                    tool_content = json.dumps(result) if not isinstance(result, str) else result
                    if len(tool_content) > 1000:
                        tool_content = tool_content[:1000] + "... [truncated]"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": fn_name,
                        "content": tool_content,
                    })

        if not final_answer and trace:
            final_answer = f"Completed {len(trace)} autonomous actions: " + ", ".join(t["tool"] for t in trace)

        return {
            "trace": trace,
            "final_answer": final_answer,
            "mode": "model-selected tools",
            "model": self.model,
            "steps": step_count,
        }
