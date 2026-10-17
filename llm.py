"""
LLM Provider Adapter for Ripple.
Provides function-calling integrations with external models (e.g. Google Gemini).
Dynamically bridges MCP tool specifications to model-specific function declarations.
Falls back to deterministic offline planners when LLM_MODE=off or API keys are missing.
"""
import os
import json
from typing import Any, Dict, List, Optional
import httpx
from config import settings

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

def mcp_tools_to_gemini_declarations(mcp_tools: List[Any]) -> List[Dict[str, Any]]:
    """Converts MCP tool definitions to Gemini function declaration format."""
    declarations = []
    for tool in mcp_tools:
        name = getattr(tool, "name", None) or tool.get("name")
        description = getattr(tool, "description", "") or tool.get("description", "")
        input_schema = getattr(tool, "inputSchema", {}) or tool.get("inputSchema", {})
        
        # Format parameters for Gemini
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])

        gemini_props = {}
        for prop_name, prop_val in properties.items():
            prop_type = prop_val.get("type", "string").upper()
            if prop_type == "ARRAY":
                gemini_props[prop_name] = {
                    "type": "ARRAY",
                    "description": prop_val.get("description", ""),
                    "items": {"type": "STRING"}
                }
            elif prop_type == "INTEGER":
                gemini_props[prop_name] = {
                    "type": "INTEGER",
                    "description": prop_val.get("description", "")
                }
            elif prop_type == "BOOLEAN":
                gemini_props[prop_name] = {
                    "type": "BOOLEAN",
                    "description": prop_val.get("description", "")
                }
            else:
                gemini_props[prop_name] = {
                    "type": "STRING",
                    "description": prop_val.get("description", "")
                }

        declarations.append({
            "name": name,
            "description": description[:1024],
            "parameters": {
                "type": "OBJECT",
                "properties": gemini_props,
                "required": required,
            }
        })
    return declarations

class GeminiFunctionCaller:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def select_tools(
        self,
        query: str,
        mcp_tools: List[Any],
        system_prompt: str = "You are a clinical evidence analyst. Select the most relevant tools."
    ) -> List[Dict[str, Any]]:
        """
        Calls Gemini with function declarations and returns the selected tool calls.
        """
        if not self.is_available():
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        declarations = mcp_tools_to_gemini_declarations(mcp_tools)

        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": query}]
                }
            ],
            "tools": [
                {
                    "function_declarations": declarations
                }
            ],
            "tool_config": {
                "function_calling_config": {
                    "mode": "AUTO"
                }
            }
        }

        url = f"{GEMINI_API_URL}?key={self.api_key}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini API returned status {resp.status_code}: {resp.text}")

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return []

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])

            tool_calls = []
            for part in parts:
                if "functionCall" in part:
                    fc = part["functionCall"]
                    tool_calls.append({
                        "tool": fc.get("name"),
                        "args": fc.get("args", {})
                    })

            return tool_calls
