"""
List available model IDs from an OpenAI-compatible endpoint (e.g. Groq, Ollama, OpenRouter).
Never prints API keys or credentials.
"""
import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv()

def list_models():
    base_url = os.getenv("LLM_BASE_URL", "").rstrip("/")
    api_key = os.getenv("LLM_API_KEY", "")

    if not base_url:
        print("Error: LLM_BASE_URL is not set.", file=sys.stderr)
        sys.exit(1)

    url = f"{base_url}/models"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = httpx.get(url, headers=headers, timeout=15.0)
        if resp.status_code != 200:
            print(f"Error: Server returned HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
            sys.exit(1)

        data = resp.json()
        models = data.get("data", [])
        if not models and isinstance(data, list):
            models = data

        print(f"Available models at {base_url} (count: {len(models)}):")
        for m in models:
            m_id = m.get("id") if isinstance(m, dict) else str(m)
            print(f"  - {m_id}")
    except Exception as e:
        print(f"Failed to fetch models from {base_url}: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    list_models()
