"""
services/claude_service.py — assembles and sends the Claude API call.

The skill's system_prompt is the system prompt; the conversation's full
message history is replayed on each turn. All calls use the platform key.
"""
import os

from anthropic import Anthropic, APIError
from fastapi import HTTPException

DEFAULT_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5")
MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "2000"))
MAX_HISTORY_MESSAGES = 40  # cap replayed history to control cost

_client = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            raise HTTPException(500, "ANTHROPIC_API_KEY is not configured on the server")
        _client = Anthropic(api_key=key)
    return _client


def call_claude(system_prompt: str, history: list, new_message: str,
                model: str = "") -> dict:
    """
    history: list of {"role": "user"|"assistant", "content": str}
    Returns {"text", "input_tokens", "output_tokens"}
    """
    messages = history[-MAX_HISTORY_MESSAGES:] + [
        {"role": "user", "content": new_message}]
    try:
        resp = get_client().messages.create(
            model=model or DEFAULT_MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        )
    except APIError as e:
        raise HTTPException(502, f"Claude API error: {getattr(e, 'message', str(e))}")

    text = "".join(b.text for b in resp.content if b.type == "text")
    return {
        "text": text,
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
    }


def generate_title(user_message: str, assistant_reply: str) -> str:
    """Short AI-generated conversation title (cheapest model, tiny call).
    Falls back to a truncated user message on any failure."""
    try:
        resp = get_client().messages.create(
            model=DEFAULT_MODEL, max_tokens=30,
            system="Generate a very short title (max 6 words) for this conversation. "
                   "Reply with the title only — no quotes, no punctuation at the end.",
            messages=[{"role": "user",
                       "content": f"User: {user_message[:300]}\nAssistant: {assistant_reply[:300]}"}],
        )
        title = "".join(b.text for b in resp.content if b.type == "text").strip()
        return title[:80] if title else user_message[:60]
    except Exception:
        return (user_message[:60] + "…") if len(user_message) > 60 else user_message
