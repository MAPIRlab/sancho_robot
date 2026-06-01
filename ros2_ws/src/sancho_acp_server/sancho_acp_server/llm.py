"""LLM creation and configuration helpers for the Sancho ACP server.

This module encapsulates LLM instantiation (ChatGoogleGenerativeAI with Vertex AI),
system prompt loading, and message history utilities (Gemini message patching).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from acp.schema import SessionMode, SessionModeState
from dotenv import load_dotenv
from google.oauth2 import service_account
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

logging.getLogger("langchain_google_genai._function_utils").setLevel(logging.ERROR)

logger = logging.getLogger("sancho_acp_server.llm")

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompt"
DEFAULT_SYSTEM_PROMPT_PATH = PROMPTS_DIR / "SYSTEM_PROMPT.md"
DEFAULT_THOUGHT_PROMPT_PATH = PROMPTS_DIR / "THOUGHT_PROMPT.md"

DEFAULT_MODEL_ID = "gemini-3.1-flash-lite"

SUPPORTED_MODELS = [
    {
        "modelId": "gemini-3.1-flash-lite",
        "name": "Gemini 3.1 Flash Lite",
        "description": "Fast and lightweight model, optimized for speed and real-time responses.",
    },
    {
        "modelId": "gemini-3-flash-preview",
        "name": "Gemini 3 Flash Preview",
        "description": "Latest Gemini 3 Flash model (preview), balanced speed and quality.",
    },
    {
        "modelId": "gemini-3.1-pro-preview",
        "name": "Gemini 3.1 Pro Preview",
        "description": "High-reasoning model for complex logical tasks and advanced tool coordination.",
    },
]

DEFAULT_MODE_ID = "interact"

SUPPORTED_MODES = [
    SessionMode(id="observe", name="Observe", description="Only look around, no movement"),
    SessionMode(id="navigate", name="Navigate", description="Move freely and explore"),
    SessionMode(id="interact", name="Interact", description="Full interaction with speech and tools"),
]

# Maps mode_id -> set of tool names that require user permission in that mode
MODE_PERMISSION_TOOLS: dict[str, set[str]] = {
    "observe": {"navigate_to_pose", "rotate_in_place"},
    "navigate": {"navigate_to_pose"},
    "interact": set(),
}

MODE_PROMPT_FILES: dict[str, str] = {
    "observe": "MODE_OBSERVE.md",
    "navigate": "MODE_NAVIGATE.md",
    "interact": "MODE_INTERACT.md",
}


def load_system_prompt() -> str:
    """Load the system prompt from disk or use a sensible default."""
    prompt_path = Path(
        os.environ.get("SANCHO_SYSTEM_PROMPT_PATH", str(DEFAULT_SYSTEM_PROMPT_PATH))
    )
    if not prompt_path.exists():
        return "You are controlling Sancho, a mobile robot. Use the MCP tools."
    return prompt_path.read_text(encoding="utf-8")


def load_thought_prompt() -> str:
    """Load the thought prompt from disk or use a sensible default."""
    prompt_path = Path(
        os.environ.get("SANCHO_THOUGHT_PROMPT_PATH", str(DEFAULT_THOUGHT_PROMPT_PATH))
    )
    if not prompt_path.exists():
        return (
            "Before taking any action, briefly describe in 1–2 sentences what you "
            "plan to do to fulfill the user's request. Be concise and specific "
            "about which tools you will use and why. Respond ONLY with the plan."
        )
    return prompt_path.read_text(encoding="utf-8")


def load_mode_prompt(mode_id: str) -> str:
    """Load the mode-specific prompt fragment from disk."""
    filename = MODE_PROMPT_FILES.get(mode_id)
    if not filename:
        return ""
    prompt_path = PROMPTS_DIR / filename
    if not prompt_path.exists():
        return ""
    return prompt_path.read_text(encoding="utf-8")


def format_ai_message(content: Any) -> str:
    """Extract human-readable text from an AI message content block."""
    if not isinstance(content, list):
        return str(content)

    parts: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type")
        if part_type == "text":
            text = part.get("text", "")
            if text:
                parts.append(text)
        elif part_type == "image_url":
            parts.append("[image]")
    return "\n".join(parts)


def build_llm(model: str | None = None) -> ChatGoogleGenerativeAI:
    """Instantiate the Google Gemini LLM using Vertex AI credentials.

    Args:
        model: The model identifier to use. Defaults to SANCHO_MCP_LLM_MODEL
               env var or DEFAULT_MODEL_ID.
    """
    load_dotenv()

    env_path = os.environ.get("SANCHO_MCP_CREDENTIALS_PATH")
    if not env_path:
        raise RuntimeError(
            "SANCHO_MCP_CREDENTIALS_PATH environment variable is not set."
        )

    credentials_path = Path(env_path)
    if not credentials_path.is_absolute():
        credentials_path = Path(__file__).resolve().parent.parent / credentials_path

    if not credentials_path.exists():
        raise RuntimeError(f"Credentials file not found at {credentials_path}")

    try:
        with open(credentials_path, "r", encoding="utf-8") as f:
            credentials_data = json.load(f)
        project_id = credentials_data.get("project_id")
        if not project_id:
            raise RuntimeError("project_id missing in service account JSON.")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON in credentials file: {e}")
    except OSError as e:
        raise RuntimeError(f"Failed to read credentials file: {e}")

    credentials = service_account.Credentials.from_service_account_file(
        str(credentials_path),
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    model = model or os.environ.get("SANCHO_MCP_LLM_MODEL", DEFAULT_MODEL_ID)
    temperature = float(os.environ.get("SANCHO_MCP_LLM_TEMPERATURE", "0.2"))

    return ChatGoogleGenerativeAI(
        model=model,
        project=project_id,
        credentials=credentials,
        vertexai=True,
        temperature=temperature,
    )


def _has_content(msg: AIMessage) -> bool:
    """Check if an AIMessage has meaningful content (text, image, etc.)."""
    if isinstance(msg.content, str):
        return bool(msg.content.strip())

    if not isinstance(msg.content, list):
        return False

    for part in msg.content:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type")
        if part_type in {"text", "image", "media", "thinking", "reasoning"}:
            if part_type == "text":
                if str(part.get("text", "")).strip():
                    return True
            else:
                return True
    return False


def _patch_empty_message(msg: AIMessage) -> AIMessage:
    """Replace empty content with a minimal placeholder."""
    if isinstance(msg.content, list):
        new_content = list(msg.content) + [{"type": "text", "text": "."}]
    else:
        new_content = "."
    return AIMessage(
        content=new_content,
        tool_calls=msg.tool_calls,
        additional_kwargs=msg.additional_kwargs,
        response_metadata=msg.response_metadata,
        id=msg.id,
    )


def ensure_non_empty_ai_messages(messages: list[Any]) -> list[Any]:
    """Patch empty AIMessages to satisfy Gemini API requirements.

    Gemini requires every message in the conversation history to have at least
    one non-empty part/content block. When using ReAct agents, LangChain might
    generate AIMessages with empty content (e.g., when the agent only calls
    a tool). This function patches empty messages by adding a minimal placeholder
    to prevent 400 Invalid Argument API errors, without losing history or context.
    """
    patched: list[Any] = []
    for msg in messages:
        if not isinstance(msg, AIMessage) or _has_content(msg):
            patched.append(msg)
        else:
            patched.append(_patch_empty_message(msg))
    return patched