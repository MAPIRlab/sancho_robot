"""SanchoAgent — ACP Agent implementation for the Sancho robot.

This module implements the ``acp.Agent`` protocol interface, handling
session lifecycle and prompt execution. Each session maintains its own
MCP connection and LangChain ReAct agent via the :class:`Orchestrator`.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from acp import (
    PROTOCOL_VERSION,
    Agent,
    AuthenticateResponse,
    InitializeResponse,
    LoadSessionResponse,
    NewSessionResponse,
    PromptResponse,
    SetSessionModeResponse,
    text_block,
    update_agent_message,
    update_agent_thought_text,
    start_tool_call,
    update_tool_call,
)
from acp.interfaces import Client
from acp.schema import (
    AgentCapabilities,
    AudioContentBlock,
    ClientCapabilities,
    EmbeddedResourceContentBlock,
    HttpMcpServer,
    ImageContentBlock,
    Implementation,
    McpServerStdio,
    ResourceContentBlock,
    SseMcpServer,
    TextContentBlock,
)

from .orchestrator import Orchestrator, SessionState

logger = logging.getLogger("sancho_acp.agent")

# Agent metadata exposed during ACP initialization.
AGENT_NAME = "sancho-acp"
AGENT_TITLE = "Sancho ACP Agent"
AGENT_VERSION = "0.1.0"


class SanchoAgent(Agent):
    """ACP server-side agent that orchestrates Sancho robot operations.

    Each connected ACP client triggers ``on_connect`` which stores the
    ``Client`` reference used for sending session updates back.
    """

    _conn: Client

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._orchestrator = Orchestrator()

    # -- ACP lifecycle -------------------------------------------------------

    def on_connect(self, conn: Client) -> None:
        """Called by the ACP SDK when a client connection is established."""
        self._conn = conn
        logger.info("ACP client connected.")

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: ClientCapabilities | None = None,
        client_info: Implementation | None = None,
        **kwargs: Any,
    ) -> InitializeResponse:
        logger.info(
            "Initialize request (protocol_version=%d, client=%s)",
            protocol_version,
            client_info.name if client_info else "unknown",
        )
        return InitializeResponse(
            protocol_version=PROTOCOL_VERSION,
            agent_capabilities=AgentCapabilities(),
            agent_info=Implementation(
                name=AGENT_NAME,
                title=AGENT_TITLE,
                version=AGENT_VERSION,
            ),
        )

    async def authenticate(
        self, method_id: str, **kwargs: Any
    ) -> AuthenticateResponse | None:
        logger.info("Authenticate request: %s", method_id)
        return AuthenticateResponse()

    # -- Session management --------------------------------------------------

    async def new_session(
        self,
        cwd: str,
        additional_directories: list[str] | None = None,
        mcp_servers: (
            list[HttpMcpServer | SseMcpServer | McpServerStdio] | None
        ) = None,
        **kwargs: Any,
    ) -> NewSessionResponse:
        session_id = uuid4().hex
        session = SessionState()
        self._sessions[session_id] = session

        self._orchestrator.init_session(session)
        logger.info("New session created: %s", session_id)
        return NewSessionResponse(session_id=session_id, modes=None)

    async def load_session(
        self,
        cwd: str,
        session_id: str,
        additional_directories: list[str] | None = None,
        mcp_servers: (
            list[HttpMcpServer | SseMcpServer | McpServerStdio] | None
        ) = None,
        **kwargs: Any,
    ) -> LoadSessionResponse | None:
        logger.info("Load session request: %s", session_id)
        if session_id not in self._sessions:
            session = SessionState()
            self._sessions[session_id] = session
            self._orchestrator.init_session(session)
        return LoadSessionResponse()

    async def set_session_mode(
        self, mode_id: str, session_id: str, **kwargs: Any
    ) -> SetSessionModeResponse | None:
        logger.info("Set session mode: %s -> %s", session_id, mode_id)
        return SetSessionModeResponse()

    # -- Prompt handling -----------------------------------------------------

    async def prompt(
        self,
        prompt: list[
            TextContentBlock
            | ImageContentBlock
            | AudioContentBlock
            | ResourceContentBlock
            | EmbeddedResourceContentBlock
        ],
        session_id: str,
        message_id: str | None = None,
        **kwargs: Any,
    ) -> PromptResponse:
        logger.info("Prompt received for session %s", session_id)

        # Ensure the session exists.
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState()
            self._orchestrator.init_session(self._sessions[session_id])

        session = self._sessions[session_id]

        # Extract text from the prompt blocks.
        user_text_parts: list[str] = []
        for block in prompt:
            if isinstance(block, TextContentBlock):
                user_text_parts.append(block.text)
            elif isinstance(block, dict):
                text = block.get("text", "")
                if text:
                    user_text_parts.append(text)

        user_text = "\n".join(user_text_parts) or "<empty prompt>"

        # Send a thought update so the client knows the agent is processing.
        await self._conn.session_update(
            session_id,
            update_agent_thought_text(
                f"Processing request: {user_text[:200]}"
            ),
        )

        # Run the ReAct loop, streaming updates back to the ACP client.
        async def on_agent_message(text: str) -> None:
            await self._conn.session_update(
                session_id, update_agent_message(text_block(text))
            )

        try:
            await self._orchestrator.run_prompt(
                session,
                user_text,
                on_agent_message=on_agent_message,
            )
        except Exception as exc:
            logger.error("Orchestrator error: %s", exc, exc_info=True)
            await self._conn.session_update(
                session_id,
                update_agent_message(
                    text_block(f"Error during execution: {exc}")
                ),
            )

        return PromptResponse(
            stop_reason="end_turn", user_message_id=message_id
        )

    # -- Cancellation --------------------------------------------------------

    async def cancel(self, session_id: str, **kwargs: Any) -> None:
        logger.info("Cancel received for session %s", session_id)
        session = self._sessions.get(session_id)
        if session is not None:
            session.cancelled.set()

    # -- Extension methods (not used, but required by protocol) --------------

    async def ext_method(
        self, method: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        logger.info("Extension method: %s", method)
        return {"status": "not_implemented"}

    async def ext_notification(
        self, method: str, params: dict[str, Any]
    ) -> None:
        logger.info("Extension notification: %s", method)
