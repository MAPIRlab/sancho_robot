"""SanchoAgent — ACP Agent implementation for the Sancho robot.

This module implements the ``acp.Agent`` protocol interface, handling
session lifecycle and prompt execution. Each session maintains its own
MCP connection and LangChain ReAct agent via the :class:`Orchestrator`.
"""

from __future__ import annotations

import datetime
import json
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
    AllowedOutcome,
    AudioContentBlock,
    ClientCapabilities,
    CloseSessionResponse,
    EmbeddedResourceContentBlock,
    ForkSessionResponse,
    HttpMcpServer,
    ImageContentBlock,
    Implementation,
    ListSessionsResponse,
    McpServerStdio,
    PermissionOption,
    ResourceContentBlock,
    ResumeSessionResponse,
    SessionCapabilities,
    SessionCloseCapabilities,
    SessionForkCapabilities,
    SessionInfo,
    SessionListCapabilities,
    SessionResumeCapabilities,
    SseMcpServer,
    TextContentBlock,
    ToolCallUpdate,
)

from .orchestrator import Orchestrator, SessionState

logger = logging.getLogger("sancho_acp_server.agent")

AGENT_NAME = "sancho-acp-server"
AGENT_TITLE = "Sancho ACP Server Agent"
AGENT_VERSION = "0.1.0"


class _SessionManager:
    """Manages session lifecycle and storage.

    Handles creation, retrieval, and cleanup of session state objects.
    """
    _sessions: dict[str, SessionState] = {}

    def __init__(self, orchestrator: Orchestrator) -> None:
        self._orchestrator = orchestrator

    def create(self, session_id: str, cwd: str) -> SessionState:
        """Create and store a new session."""
        session = SessionState()
        session.cwd = cwd
        session.updated_at = datetime.datetime.utcnow().isoformat() + "Z"
        session.title = f"Session {session_id[:8]}"
        self._sessions[session_id] = session
        self._orchestrator.init_session(session)
        return session

    def get_or_create(self, session_id: str, cwd: str) -> SessionState:
        """Get existing session or create a new one."""
        if session_id in self._sessions:
            self._sessions[session_id].updated_at = (
                datetime.datetime.utcnow().isoformat() + "Z"
            )
            return self._sessions[session_id]
        return self.create(session_id, cwd)

    def get(self, session_id: str) -> SessionState | None:
        """Retrieve a session by ID."""
        return self._sessions.get(session_id)

    async def close(self, session_id: str) -> None:
        """Remove and teardown a session."""
        session = self._sessions.pop(session_id, None)
        if session is not None:
            await self._orchestrator.teardown_session(session)

    def list_all(self) -> list[SessionInfo]:
        """List all sessions sorted by update time (newest first)."""
        now = datetime.datetime.utcnow().isoformat() + "Z"
        sessions_list = [
            SessionInfo(
                sessionId=sid,
                cwd=session.cwd,
                title=session.title,
                updatedAt=session.updated_at or now,
                additionalDirectories=None,
            )
            for sid, session in self._sessions.items()
        ]
        sessions_list.sort(key=lambda s: s.updatedAt or "", reverse=True)
        return sessions_list

    def fork(self, source_id: str, new_id: str, cwd: str) -> SessionState:
        """Fork an existing session into a new one."""
        source = self._sessions[source_id]
        new_state = self.create(new_id, cwd)
        new_state.messages = list(source.messages)
        return new_state


class SanchoAgent(Agent):
    """ACP server-side agent that orchestrates Sancho robot operations.

    Each connected ACP client triggers ``on_connect`` which stores the
    ``Client`` reference used for sending session updates back.
    """

    _conn: Client

    def __init__(self) -> None:
        self._orchestrator = Orchestrator()
        self._session_mgr = _SessionManager(self._orchestrator)

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
            agent_capabilities=AgentCapabilities(
                loadSession=True,
                sessionCapabilities=SessionCapabilities(
                    list=SessionListCapabilities(),
                    fork=SessionForkCapabilities(),
                    resume=SessionResumeCapabilities(),
                    close=SessionCloseCapabilities(),
                ),
            ),
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

    async def new_session(
        self,
        cwd: str,
        additional_directories: list[str] | None = None,
        mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio] | None = None,
        **kwargs: Any,
    ) -> NewSessionResponse:
        session_id = uuid4().hex
        self._session_mgr.create(session_id, cwd)
        logger.info("New session created: %s", session_id)
        return NewSessionResponse(session_id=session_id, modes=None)

    async def load_session(
        self,
        cwd: str,
        session_id: str,
        additional_directories: list[str] | None = None,
        mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio] | None = None,
        **kwargs: Any,
    ) -> LoadSessionResponse | None:
        logger.info("Load session request: %s", session_id)
        self._session_mgr.get_or_create(session_id, cwd)
        return LoadSessionResponse()

    async def list_sessions(
        self,
        additional_directories: list[str] | None = None,
        cursor: str | None = None,
        cwd: str | None = None,
        **kwargs: Any,
    ) -> ListSessionsResponse:
        logger.info("List sessions request (cwd=%s, cursor=%s)", cwd, cursor)
        return ListSessionsResponse(sessions=self._session_mgr.list_all())

    async def fork_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio] | None = None,
        **kwargs: Any,
    ) -> ForkSessionResponse:
        logger.info("Fork session: source=%s", session_id)
        self._session_mgr.get_or_create(session_id, cwd)
        new_session_id = uuid4().hex
        self._session_mgr.fork(session_id, new_session_id, cwd)
        return ForkSessionResponse(sessionId=new_session_id)

    async def resume_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio] | None = None,
        **kwargs: Any,
    ) -> ResumeSessionResponse:
        logger.info("Resume session: %s (cwd=%s)", session_id, cwd)
        self._session_mgr.get_or_create(session_id, cwd)
        return ResumeSessionResponse()

    async def close_session(
        self, session_id: str, **kwargs: Any
    ) -> CloseSessionResponse:
        logger.info("Close session: %s", session_id)
        await self._session_mgr.close(session_id)
        return CloseSessionResponse()

    async def set_session_mode(
        self, mode_id: str, session_id: str, **kwargs: Any
    ) -> SetSessionModeResponse | None:
        logger.info("Set session mode: %s -> %s", session_id, mode_id)
        return SetSessionModeResponse()

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
        try:
            session = self._session_mgr.get_or_create(session_id, "/tmp")

            user_text = self._extract_user_text(prompt)

            thought_text = await self._orchestrator.generate_thought(session, user_text)
            await self._conn.session_update(
                session_id, update_agent_thought_text(thought_text)
            )

            await self._orchestrator.run_prompt(
                session,
                user_text=user_text,
                thought_text=thought_text,
                on_agent_message=self._make_on_agent_message(session_id),
                on_tool_start=self._make_on_tool_start(session_id),
                on_tool_end=self._make_on_tool_end(session_id),
                permission_callback=self._make_permission_callback(session_id),
            )

            session.updated_at = datetime.datetime.utcnow().isoformat() + "Z"
            return PromptResponse(stop_reason="end_turn", user_message_id=message_id)
        except Exception as e:
            logger.exception("CRITICAL ERROR IN PROMPT:")
            raise e

    def _extract_user_text(
        self,
        prompt: list[TextContentBlock | ImageContentBlock | AudioContentBlock | ResourceContentBlock | EmbeddedResourceContentBlock],
    ) -> str:
        """Extract text content from prompt blocks."""
        parts = []
        for block in prompt:
            if isinstance(block, TextContentBlock):
                parts.append(block.text)
            elif isinstance(block, dict):
                text = block.get("text", "")
                if text:
                    parts.append(text)
        return "\n".join(parts) or "<empty prompt>"

    def _make_on_agent_message(self, session_id: str):
        async def on_agent_message(text: str) -> None:
            await self._conn.session_update(
                session_id, update_agent_message(text_block(text))
            )
        return on_agent_message

    def _make_on_tool_start(self, session_id: str):
        async def on_tool_start(
            tool_call_id: str, tool_name: str, input_str: str
        ) -> None:
            await self._conn.session_update(
                session_id,
                start_tool_call(
                    tool_call_id=tool_call_id,
                    title=tool_name,
                    status="in_progress",
                    raw_input=input_str,
                ),
            )
        return on_tool_start

    def _make_on_tool_end(self, session_id: str):
        async def on_tool_end(
            tool_call_id: str, tool_name: str, output_summary: str
        ) -> None:
            await self._conn.session_update(
                session_id,
                update_tool_call(
                    tool_call_id=tool_call_id,
                    title=tool_name,
                    status="completed",
                    raw_output=output_summary,
                ),
            )
        return on_tool_end

    def _make_permission_callback(self, session_id: str):
        async def request_permission(
            tool_name: str, tool_args: dict[str, Any]
        ) -> bool:
            perm_id = uuid4().hex[:12]
            options = [
                PermissionOption(
                    option_id="approve",
                    name="Approve",
                    kind="allow_once",
                ),
                PermissionOption(
                    option_id="reject",
                    name="Reject",
                    kind="reject_once",
                ),
            ]
            tool_call_info = ToolCallUpdate(
                tool_call_id=perm_id,
                title=tool_name,
                status="pending",
                raw_input=json.dumps(tool_args, ensure_ascii=False),
            )
            try:
                resp = await self._conn.request_permission(
                    options=options,
                    session_id=session_id,
                    tool_call=tool_call_info,
                )
                approved = isinstance(resp.outcome, AllowedOutcome)
                logger.info(
                    "Permission for %s: %s",
                    tool_name,
                    "approved" if approved else "denied",
                )
                return approved
            except Exception as exc:
                logger.error("Permission request failed for %s: %s", tool_name, exc)
                return False
        return request_permission

    async def cancel(self, session_id: str, **kwargs: Any) -> None:
        logger.info("Cancel received for session %s", session_id)
        session = self._session_mgr.get(session_id)
        if session is not None:
            session.cancelled.set()

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        logger.info("Extension method: %s", method)
        return {"status": "not_implemented"}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        logger.info("Extension notification: %s", method)