"""ReAct orchestrator that bridges ACP sessions with MCP tools via LangChain.

This module encapsulates the LLM reasoning loop. It connects to the MCP
server, loads available tools, wraps multimodal payloads, and runs a ReAct
agent that streams its progress back through ACP session updates.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_mcp_adapters.sessions import create_session
from langchain_mcp_adapters.tools import load_mcp_tools

from .llm import (
    build_llm,
    load_system_prompt,
    load_thought_prompt,
    ensure_non_empty_ai_messages,
    format_ai_message,
)
from .tools import (
    wrap_take_photo,
    wrap_all_tools,
    ToolLogger,
    ToolStartCallback,
    ToolEndCallback,
    PermissionCallback,
)

logger = logging.getLogger("sancho_acp_server.orchestrator")


@dataclass
class SessionState:
    """Holds per-session state: chat history, agent, and cancellation flag."""

    messages: list[Any] = field(default_factory=list)
    agent: Any = None
    cancelled: asyncio.Event = field(default_factory=asyncio.Event)
    mcp_session: Any = None
    mcp_context: Any = None
    on_tool_start: ToolStartCallback | None = None
    on_tool_end: ToolEndCallback | None = None
    permission_callback: PermissionCallback | None = None

    def reset_cancel(self) -> None:
        self.cancelled.clear()


class Orchestrator:
    """Manages MCP connections and runs the ReAct agent loop for a session."""

    def __init__(self) -> None:
        self.llm = build_llm()
        self.server_url = os.environ.get(
            "SANCHO_MCP_SERVER_URL", "http://127.0.0.1:8000/mcp"
        )
        self._system_prompt = load_system_prompt()

    def init_session(self, session: SessionState) -> None:
        """Initialize a session with the system prompt (no MCP yet).

        MCP connection is deferred to the first ``run_prompt`` call so
        that ``new_session`` completes instantly even when the MCP server
        is not yet available.
        """
        session.messages = [SystemMessage(content=self._system_prompt)]
        logger.info("Session created (MCP connection deferred).")

    async def _ensure_mcp(self, session: SessionState) -> None:
        """Lazily connect to MCP, load tools, and build the agent."""
        if session.agent is not None:
            return

        logger.info("Connecting to MCP server at %s ...", self.server_url)
        session.mcp_context = create_session({
            "transport": "streamable_http",
            "url": self.server_url,
        })
        session.mcp_session = await session.mcp_context.__aenter__()
        await session.mcp_session.initialize()

        tools = wrap_take_photo(await load_mcp_tools(session.mcp_session))
        tools = wrap_all_tools(
            tools,
            on_tool_start=self._proxy_tool_start(session),
            on_tool_end=self._proxy_tool_end(session),
            permission_callback=self._proxy_permission(session),
        )

        session.agent = create_agent(self.llm, tools)
        logger.info("MCP connected — %d tools loaded from %s", len(tools), self.server_url)

    def _proxy_tool_start(self, session: SessionState) -> ToolStartCallback | None:
        async def proxy(tool_call_id: str, name: str, input_summary: str) -> None:
            if session.on_tool_start:
                await session.on_tool_start(tool_call_id, name, input_summary)
        return proxy

    def _proxy_tool_end(self, session: SessionState) -> ToolEndCallback | None:
        async def proxy(tool_call_id: str, name: str, output: str) -> None:
            if session.on_tool_end:
                await session.on_tool_end(tool_call_id, name, output)
        return proxy

    def _proxy_permission(self, session: SessionState) -> PermissionCallback | None:
        async def proxy(tool_name: str, tool_args: dict[str, Any]) -> bool:
            if session.permission_callback:
                return await session.permission_callback(tool_name, tool_args)
            return False
        return proxy

    async def teardown_session(self, session: SessionState) -> None:
        """Close the MCP session context."""
        if session.mcp_context is not None:
            try:
                await session.mcp_context.__aexit__(None, None, None)
            except Exception:
                logger.debug("MCP context cleanup error", exc_info=True)
            session.mcp_context = None
            session.mcp_session = None

    async def generate_thought(self, session: SessionState, user_text: str) -> str:
        """Generate a brief preliminary thought about the planned actions.

        Uses a lightweight LLM call with the current conversation context
        plus a meta-prompt.
        """
        thought_prompt = load_thought_prompt()
        thought_messages = list(session.messages) + [
            HumanMessage(content=f"{thought_prompt}\n\nUser request:\n{user_text}"),
        ]

        try:
            response = await self.llm.ainvoke(thought_messages)
            thought_text = format_ai_message(response.content)
        except Exception as exc:
            logger.warning("Failed to generate preliminary thought: %s", exc)
            thought_text = f"Processing: {user_text[:200]}"

        if not thought_text.strip():
            thought_text = f"Processing: {user_text[:200]}"

        logger.info("Preliminary thought: %s", thought_text)
        return thought_text

    async def run_prompt(
        self,
        session: SessionState,
        user_text: str,
        thought_text: str,
        on_agent_message: Callable[[str], Awaitable[None]] | None = None,
        on_tool_start: ToolStartCallback | None = None,
        on_tool_end: ToolEndCallback | None = None,
        permission_callback: PermissionCallback | None = None,
    ) -> str:
        """Execute a single user prompt through the ReAct agent loop.

        Args:
            session: The per-session state.
            user_text: The natural language instruction from the user.
            thought_text: The preliminary thought plan generated for this turn.
            on_agent_message: Async callback ``(text) -> None`` called when
                the agent produces a text response.
            on_tool_start: Async callback ``(tool_call_id, name, input) -> None``
                called when a tool starts executing.
            on_tool_end: Async callback ``(tool_call_id, name, output) -> None``
                called when a tool finishes.
            permission_callback: Async callback ``(tool_name, args) -> bool``
                for gating sensitive tools behind user permission.

        Returns:
            The final text response from the agent.
        """
        session.on_tool_start = on_tool_start
        session.on_tool_end = on_tool_end
        session.permission_callback = permission_callback

        await self._ensure_mcp(session)
        session.reset_cancel()

        if session.cancelled.is_set():
            return "Task cancelled."

        start_index = len(session.messages)

        plan_instruction = (
            f"You must follow this preliminary plan to address the user's request:\n"
            f"\"\"\"\n{thought_text}\n\"\"\"\n"
            f"Call the corresponding tools to execute this plan.\n\n"
            f"User request:\n{user_text}"
        )
        exec_messages = list(session.messages) + [HumanMessage(content=plan_instruction)]

        callback = ToolLogger()
        logger.info("Executing agent.ainvoke with %d messages...", len(exec_messages))
        result = await session.agent.ainvoke(
            {"messages": exec_messages},
            config={"callbacks": [callback]},
        )
        logger.info("agent.ainvoke finished.")

        new_messages = result.get("messages", [])
        logger.info("Generated %d new messages during this turn.", len(new_messages) - len(exec_messages))

        generated_messages = new_messages[start_index + 1:]

        reply = next((msg for msg in reversed(generated_messages) if isinstance(msg, AIMessage)), None)
        reply_text = format_ai_message(reply.content) if reply is not None else ""

        self._prepend_thought(generated_messages, thought_text)

        session.messages = list(session.messages) + [HumanMessage(content=user_text)] + generated_messages
        session.messages = ensure_non_empty_ai_messages(session.messages)

        if on_agent_message and reply_text:
            await on_agent_message(reply_text)

        return reply_text

    def _prepend_thought(self, generated_messages: list[Any], thought_text: str) -> None:
        """Prepend thought_text to the last AIMessage in the generated messages."""
        for msg in reversed(generated_messages):
            if isinstance(msg, AIMessage):
                if isinstance(msg.content, list):
                    msg.content = [{"type": "text", "text": f"{thought_text}\n"}] + list(msg.content)
                elif isinstance(msg.content, str):
                    msg.content = thought_text if not msg.content.strip() else f"{thought_text}\n\n{msg.content}"
                else:
                    msg.content = f"{thought_text}\n\n{msg.content}"
                break