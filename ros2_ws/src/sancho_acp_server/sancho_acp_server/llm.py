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

from dotenv import load_dotenv
from google.oauth2 import service_account
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

# Silence langchain_google_genai schema warnings.
logging.getLogger("langchain_google_genai._function_utils").setLevel(
    logging.ERROR
)

logger = logging.getLogger("sancho_acp_server.llm")

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompt"
DEFAULT_SYSTEM_PROMPT_PATH = PROMPTS_DIR / "SYSTEM_PROMPT.md"
DEFAULT_THOUGHT_PROMPT_PATH = PROMPTS_DIR / "THOUGHT_PROMPT.md"


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


def _format_ai_message(content: Any) -> str:
    """Extract human-readable text from an AI message content block."""
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    parts.append(str(part.get("text", "")))
                elif part.get("type") == "image_url":
                    parts.append("[image]")
        return "\n".join(p for p in parts if p)
    return str(content)


def build_llm() -> ChatGoogleGenerativeAI:
    """Instantiate the Google Gemini LLM using Vertex AI credentials from environment variables."""
    load_dotenv()

    # Locate and read service account credentials for Vertex AI
    env_path = os.environ.get("SANCHO_MCP_CREDENTIALS_PATH")
    if not env_path:
        raise RuntimeError(
            "SANCHO_MCP_CREDENTIALS_PATH environment variable is not set in the environment or .env file."
        )

    credentials_path = Path(env_path)
    if not credentials_path.is_absolute():
        # Resolve relative to the sancho_acp_server root directory (parent of sancho_acp_server package directory)
        credentials_path = Path(__file__).resolve().parent.parent / credentials_path

    if not credentials_path.exists():
        raise RuntimeError(f"Credentials file not found at {credentials_path}")

    try:
        with open(credentials_path, "r", encoding="utf-8") as f:
            credentials_data = json.load(f)
        project_id = credentials_data.get("project_id")
        if not project_id:
            raise RuntimeError("project_id missing in service account JSON.")
    except Exception as e:
        raise RuntimeError(f"Failed to read service account credentials: {e}")

    credentials = service_account.Credentials.from_service_account_file(
        str(credentials_path),
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    model = os.environ.get("SANCHO_MCP_LLM_MODEL", "gemini-3.1-flash-lite")
    temperature = float(
        os.environ.get("SANCHO_MCP_LLM_TEMPERATURE", "0.2")
    )

    return ChatGoogleGenerativeAI(
        model=model,
        project=project_id,
        credentials=credentials,
        vertexai=True,
        temperature=temperature,
    )


def _ensure_non_empty_ai_messages(messages: list[Any]) -> list[Any]:
    """Gemini API requires that every message in the conversation history has at least
    one non-empty part/content block. When using ReAct agents, LangGraph/LangChain
    might generate AIMessages with empty text content (e.g., when the agent only calls
    a tool). This function patches any empty AIMessage by adding a minimal text placeholder
    to prevent 400 Invalid Argument API crashes, without deleting history or losing context.
    """
    patched_messages = []
    for msg in messages:
        if not isinstance(msg, AIMessage):
            patched_messages.append(msg)
            continue

        has_text_or_media = False
        if isinstance(msg.content, str):
            has_text_or_media = bool(msg.content.strip())
        elif isinstance(msg.content, list):
            for part in msg.content:
                if isinstance(part, str) and part.strip():
                    has_text_or_media = True
                    break
                if isinstance(part, dict) and part.get("type") in {
                    "text",
                    "image",
                    "media",
                    "thinking",
                    "reasoning",
                }:
                    # If it's a text block, ensure the text itself is not empty
                    if part.get("type") == "text" and not str(part.get("text", "")).strip():
                        continue
                    has_text_or_media = True
                    break

        if not has_text_or_media:
            # Replace empty content with a minimal placeholder to satisfy Gemini's API schema
            if isinstance(msg.content, list):
                new_content = list(msg.content) + [{"type": "text", "text": "."}]
            else:
                new_content = "."
            msg = AIMessage(
                content=new_content,
                tool_calls=msg.tool_calls,
                additional_kwargs=msg.additional_kwargs,
                response_metadata=msg.response_metadata,
                id=msg.id,
            )
        patched_messages.append(msg)
    return patched_messages
