"""ReAct orchestrator that bridges ACP sessions with MCP tools via LangChain.

This module encapsulates the LLM reasoning loop. It connects to the MCP
server, loads available tools, wraps multimodal payloads, and runs a ReAct
agent that streams its progress back through ACP session updates.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.sessions import create_session
from langchain_mcp_adapters.tools import load_mcp_tools

# Silence langchain_google_genai schema warnings.
logging.getLogger("langchain_google_genai._function_utils").setLevel(
    logging.ERROR
)

logger = logging.getLogger("sancho_acp.orchestrator")

DEFAULT_PROMPT_PATH = Path(__file__).resolve().parent.parent / "SYSTEM_PROMPT.md"

# Tools that require explicit human authorization via ACP before execution.
SENSITIVE_TOOLS: set[str] = {
    "navigate_to_pose",
    "speak",
    "mission_random_move",
    "mission_move_and_talk",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_system_prompt() -> str:
    """Load the system prompt from disk or use a sensible default."""
    prompt_path = Path(
        os.environ.get("SANCHO_SYSTEM_PROMPT_PATH", str(DEFAULT_PROMPT_PATH))
    )
    if not prompt_path.exists():
        return "You are controlling Sancho, a mobile robot. Use the MCP tools."
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


def _summarize_tool_output(output: Any) -> str:
    """Create a short summary of a tool's return value for logging."""
    if isinstance(output, list):
        for part in output:
            if isinstance(part, dict) and part.get("type") == "image_url":
                return "<image payload>"
        return str(output)
    if isinstance(output, dict):
        if output.get("type") == "image":
            data_len = len(str(output.get("data", "")))
            return f"<image payload bytes={data_len}>"
        if "error" in output:
            return f"error: {output['error']}"
    text = str(output)
    return text if len(text) <= 500 else f"{text[:500]}..."


# ---------------------------------------------------------------------------
# Multimodal image handling (same as sancho_mcp_client)
# ---------------------------------------------------------------------------

def _mcp_image_payload_to_content(payload: Any) -> Any:
    """Convert MCP image payloads into LangChain multimodal content blocks."""
    if isinstance(payload, list):
        new_blocks = []
        for block in payload:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                try:
                    data = json.loads(text)
                    if isinstance(data, dict) and data.get("type") == "image":
                        new_blocks.extend(_create_multimodal_content(data))
                        continue
                except json.JSONDecodeError:
                    pass
            new_blocks.append(block)
        return new_blocks

    if isinstance(payload, str):
        try:
            data = json.loads(payload)
            if isinstance(data, dict) and data.get("type") == "image":
                return _create_multimodal_content(data)
        except json.JSONDecodeError:
            pass

    if isinstance(payload, dict) and payload.get("type") == "image":
        return _create_multimodal_content(payload)

    return payload


def _create_multimodal_content(data: dict) -> list[dict]:
    b64_data = data.get("data")
    if not b64_data:
        return [{"type": "text", "text": "error: Empty image payload"}]
    mime = data.get("mime_type") or data.get("mimeType") or "image/jpeg"
    data_url = f"data:{mime};base64,{b64_data}"
    return [
        {"type": "text", "text": "Captured image from robot camera."},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]


async def _call_tool(tool: Any, args: dict) -> Any:
    """Invoke a LangChain tool, handling both sync and async variants."""
    if hasattr(tool, "ainvoke"):
        return await tool.ainvoke(args)
    return await asyncio.to_thread(tool.invoke, args)


def _wrap_take_photo(tools: list[Any]) -> list[Any]:
    """Wrap the ``take_photo`` tool so its raw base64 image is converted
    into a multimodal content block that the LLM can interpret directly."""
    tool_map = {tool.name: tool for tool in tools}
    raw_tool = tool_map.get("take_photo")
    if raw_tool is None:
        return tools

    async def _take_photo() -> Any:
        payload = await _call_tool(raw_tool, {})
        return _mcp_image_payload_to_content(payload)

    wrapped = StructuredTool.from_function(
        name="take_photo",
        description=(
            raw_tool.description
            or "Capture a camera frame as an image payload."
        ),
        coroutine=_take_photo,
    )
    return [t for t in tools if t.name != "take_photo"] + [wrapped]


# ---------------------------------------------------------------------------
# LLM builder
# ---------------------------------------------------------------------------

def build_llm() -> ChatGoogleGenerativeAI:
    """Instantiate the Google Gemini LLM from environment variables."""
    load_dotenv()
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is required for Gemini.")

    model = os.environ.get("SANCHO_MCP_LLM_MODEL", "gemini-3.1-flash-lite")
    temperature = float(
        os.environ.get("SANCHO_MCP_LLM_TEMPERATURE", "0.2")
    )

    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        temperature=temperature,
    )


# ---------------------------------------------------------------------------
# Tool callback logger (for server-side console)
# ---------------------------------------------------------------------------

class ToolLogger(BaseCallbackHandler):
    """Prints tool invocation traces to the server console."""

    def on_tool_start(
        self, serialized: dict, input_str: str, **kwargs: Any
    ) -> None:
        name = serialized.get("name", "tool")
        logger.info("[tool:start] %s <- %s", name, input_str)

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        name = kwargs.get("name", "tool")
        logger.info("[tool:end] %s -> %s", name, _summarize_tool_output(output))


# ---------------------------------------------------------------------------
# Session state container
# ---------------------------------------------------------------------------

class SessionState:
    """Holds per-session state: chat history, agent, and cancellation flag."""

    def __init__(self) -> None:
        self.messages: list[Any] = []
        self.agent: Any = None
        self.cancelled = asyncio.Event()
        self.mcp_session: Any = None
        self.mcp_context: Any = None

    def reset_cancel(self) -> None:
        self.cancelled.clear()


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class Orchestrator:
    """Manages MCP connections and runs the ReAct agent loop for a session."""

    def __init__(self) -> None:
        self.llm = build_llm()
        self.system_prompt = load_system_prompt()
        self.server_url = os.environ.get(
            "SANCHO_MCP_SERVER_URL", "http://127.0.0.1:8000/mcp"
        )

    def init_session(self, session: SessionState) -> None:
        """Initialize a session with the system prompt (no MCP yet).

        MCP connection is deferred to the first ``run_prompt`` call so
        that ``new_session`` completes instantly even when the MCP server
        is not yet available.
        """
        session.messages = [SystemMessage(content=self.system_prompt)]
        logger.info("Session created (MCP connection deferred).")

    async def _ensure_mcp(self, session: SessionState) -> None:
        """Lazily connect to MCP, load tools, and build the agent."""
        if session.agent is not None:
            return  # Already connected.

        logger.info("Connecting to MCP server at %s ...", self.server_url)
        connection = {
            "transport": "streamable_http",
            "url": self.server_url,
        }
        session.mcp_context = create_session(connection)
        session.mcp_session = await session.mcp_context.__aenter__()
        await session.mcp_session.initialize()

        tools = _wrap_take_photo(await load_mcp_tools(session.mcp_session))
        session.agent = create_agent(self.llm, tools)
        logger.info(
            "MCP connected — %d tools loaded from %s",
            len(tools),
            self.server_url,
        )

    async def teardown_session(self, session: SessionState) -> None:
        """Close the MCP session context."""
        if session.mcp_context is not None:
            try:
                await session.mcp_context.__aexit__(None, None, None)
            except Exception:
                logger.debug("MCP context cleanup error", exc_info=True)
            session.mcp_context = None
            session.mcp_session = None

    async def run_prompt(
        self,
        session: SessionState,
        user_text: str,
        on_agent_message: Any = None,
        on_tool_start: Any = None,
        on_tool_end: Any = None,
    ) -> str:
        """Execute a single user prompt through the ReAct agent loop.

        The MCP connection and tool loading happen lazily on the first
        call, so the system tolerates starting before the MCP server.

        Args:
            session: The per-session state.
            user_text: The natural language instruction from the user.
            on_agent_message: Async callback ``(text: str) -> None`` called
                when the agent produces a text response.
            on_tool_start: Async callback ``(name: str, input: str) -> None``
                called when a tool starts executing.
            on_tool_end: Async callback ``(name: str, output: str) -> None``
                called when a tool finishes.

        Returns:
            The final text response from the agent.
        """
        # Lazily establish the MCP connection on first prompt.
        await self._ensure_mcp(session)

        session.reset_cancel()
        callback = ToolLogger()

        session.messages.append(HumanMessage(content=user_text))

        if session.cancelled.is_set():
            return "Task cancelled."

        result = await session.agent.ainvoke(
            {"messages": session.messages},
            config={"callbacks": [callback]},
        )
        session.messages = result.get("messages", session.messages)

        reply = next(
            (
                msg
                for msg in reversed(session.messages)
                if isinstance(msg, AIMessage)
            ),
            None,
        )
        reply_text = (
            _format_ai_message(reply.content) if reply is not None else ""
        )

        if on_agent_message and reply_text:
            await on_agent_message(reply_text)

        return reply_text
