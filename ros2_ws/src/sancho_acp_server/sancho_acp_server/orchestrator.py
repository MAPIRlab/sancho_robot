"""ReAct orchestrator that bridges ACP sessions with MCP tools via LangChain.

This module encapsulates the LLM reasoning loop. It connects to the MCP
server, loads available tools, wraps multimodal payloads, and runs a ReAct
agent that streams its progress back through ACP session updates.
"""

from __future__ import annotations

import logging
import os
import asyncio
from typing import Any, Callable, Awaitable
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_mcp_adapters.sessions import create_session
from langchain_mcp_adapters.tools import load_mcp_tools

from .llm import (
    build_llm,
    load_system_prompt,
    load_thought_prompt,
    _ensure_non_empty_ai_messages,
    _format_ai_message,
)
from .tools import (
    _wrap_take_photo,
    _wrap_all_tools,
    ToolLogger,
    ToolStartCallback,
    ToolEndCallback,
    PermissionCallback,
)

logger = logging.getLogger("sancho_acp_server.orchestrator")

# The preliminary thought meta-prompt is loaded dynamically from THOUGHT_PROMPT.md.


class SessionState:
    """Holds per-session state: chat history, agent, and cancellation flag."""

    def __init__(self) -> None:
        self.messages: list[Any] = []
        self.agent: Any = None
        self.cancelled = asyncio.Event()
        self.mcp_session: Any = None
        self.mcp_context: Any = None
        # References to active streaming/permission callbacks (updated each prompt)
        self.on_tool_start: ToolStartCallback | None = None
        self.on_tool_end: ToolEndCallback | None = None
        self.permission_callback: PermissionCallback | None = None

    def reset_cancel(self) -> None:
        self.cancelled.clear()


class Orchestrator:
    """Manages MCP connections and runs the ReAct agent loop for a session."""

    def __init__(self) -> None:
        self.llm = build_llm()
        self.server_url = os.environ.get(
            "SANCHO_MCP_SERVER_URL", "http://127.0.0.1:8000/mcp"
        )

    def init_session(self, session: SessionState) -> None:
        """Initialize a session with the system prompt (no MCP yet).

        MCP connection is deferred to the first ``run_prompt`` call so
        that ``new_session`` completes instantly even when the MCP server
        is not yet available.
        """
        session.messages = [SystemMessage(content=load_system_prompt())]
        logger.info("Session created (MCP connection deferred).")

    async def _ensure_mcp(
        self,
        session: SessionState,
    ) -> None:
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

        # Dynamic proxy callbacks that always route to the session's active connection
        async def proxy_tool_start(tool_call_id: str, name: str, input_summary: str) -> None:
            cb = getattr(session, "on_tool_start", None)
            if cb:
                await cb(tool_call_id, name, input_summary)

        async def proxy_tool_end(tool_call_id: str, name: str, output: str) -> None:
            cb = getattr(session, "on_tool_end", None)
            if cb:
                await cb(tool_call_id, name, output)

        async def proxy_permission_callback(tool_name: str, tool_args: dict[str, Any]) -> bool:
            cb = getattr(session, "permission_callback", None)
            if cb:
                return await cb(tool_name, tool_args)
            return False

        # Wrap every tool for ACP streaming + permission gating.
        tools = _wrap_all_tools(
            tools,
            on_tool_start=proxy_tool_start,
            on_tool_end=proxy_tool_end,
            permission_callback=proxy_permission_callback,
        )

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

    # ----- Preliminary thought generation -----------------------------------

    async def generate_thought(
        self, session: SessionState, user_text: str
    ) -> str:
        """Generate a brief preliminary thought about the planned actions.

        Uses a lightweight LLM call with the current conversation context
        plus a meta-prompt.

        Returns:
            The thought text.
        """
        thought_prompt = load_thought_prompt()
        thought_messages = list(session.messages) + [
            HumanMessage(
                content=f"{thought_prompt}\n\nUser request:\n{user_text}"
            ),
        ]

        try:
            response = await self.llm.ainvoke(thought_messages)
            thought_text = _format_ai_message(response.content)
        except Exception as exc:
            logger.warning("Failed to generate preliminary thought: %s", exc)
            thought_text = f"Processing: {user_text[:200]}"

        if not thought_text.strip():
            thought_text = f"Processing: {user_text[:200]}"

        logger.info("Preliminary thought: %s", thought_text)
        return thought_text

    # ----- Main prompt execution --------------------------------------------

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
        # Store current active callbacks on the session so the proxy functions can access them.
        session.on_tool_start = on_tool_start
        session.on_tool_end = on_tool_end
        session.permission_callback = permission_callback

        # Lazily establish the MCP connection on first prompt.
        await self._ensure_mcp(session)

        session.reset_cancel()

        if session.cancelled.is_set():
            return "Task cancelled."

        # Keep track of where our new messages start in session history
        start_index = len(session.messages)

        plan_instruction = (
            f"You must follow this preliminary plan to address the user's request:\n"
            f"\"\"\"\n{thought_text}\n\"\"\"\n"
            f"Call the corresponding tools to execute this plan.\n\n"
            f"User request:\n{user_text}"
        )
        exec_messages = list(session.messages) + [
            HumanMessage(content=plan_instruction)
        ]

        callback = ToolLogger()
        logger.info("Executing agent.ainvoke with %d messages...", len(exec_messages))
        result = await session.agent.ainvoke(
            {"messages": exec_messages},
            config={"callbacks": [callback]},
        )
        logger.info("agent.ainvoke finished.")

        new_messages = result.get("messages", [])
        logger.info("Generated %d new messages during this turn.", len(new_messages) - len(exec_messages))

        # Extract the messages generated during this run (skip HumanMessage plan)
        generated_messages = new_messages[start_index + 1:]

        # Find the clean final response before prepending the thought (to send to the user)
        reply = next(
            (
                msg
                for msg in reversed(generated_messages)
                if isinstance(msg, AIMessage)
            ),
            None,
        )
        reply_text = (
            _format_ai_message(reply.content) if reply is not None else ""
        )

        # Prepend the thought_text to the last AIMessage of this turn (the final response) for session history storage
        for msg in reversed(generated_messages):
            if isinstance(msg, AIMessage):
                logger.info("Prepending thought_text to last AIMessage in session history. Original content type: %s", type(msg.content))
                if isinstance(msg.content, list):
                    msg.content = [{"type": "text", "text": f"{thought_text}\n"}] + list(msg.content)
                elif isinstance(msg.content, str):
                    if not msg.content.strip():
                        msg.content = thought_text
                    else:
                        msg.content = f"{thought_text}\n\n{msg.content}"
                else:
                    msg.content = f"{thought_text}\n\n{msg.content}"
                break

        # Reconstruct session messages: original_history + HumanMessage + generated_messages
        session.messages = list(session.messages) + [HumanMessage(content=user_text)] + generated_messages
        session.messages = _ensure_non_empty_ai_messages(session.messages)

        if on_agent_message and reply_text:
            await on_agent_message(reply_text)

        return reply_text
