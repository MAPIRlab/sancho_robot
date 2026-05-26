"""Non-interactive smoke test: connect, initialize, new_session, disconnect.

This test validates the ACP protocol handshake works correctly over TCP
without requiring the MCP server to be running.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from acp import PROTOCOL_VERSION, connect_to_agent, Client, RequestError
from acp.schema import (
    AgentMessageChunk,
    AgentThoughtChunk,
    AvailableCommandsUpdate,
    ClientCapabilities,
    ConfigOptionUpdate,
    CurrentModeUpdate,
    EnvVariable,
    Implementation,
    PermissionOption,
    SessionInfoUpdate,
    ToolCallProgress,
    ToolCallStart,
    ToolCallUpdate,
    UsageUpdate,
    UserMessageChunk,
    CreateTerminalResponse,
    KillTerminalResponse,
    ReadTextFileResponse,
    ReleaseTerminalResponse,
    RequestPermissionResponse,
    TerminalOutputResponse,
    WaitForTerminalExitResponse,
    WriteTextFileResponse,
)


class MinimalClient(Client):
    """Stub client that logs updates."""

    async def session_update(self, session_id, update, **kwargs):
        pass

    async def request_permission(self, options, session_id, tool_call, **kwargs):
        from acp.schema import DeniedOutcome
        return RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))

    async def write_text_file(self, content, path, session_id, **kwargs):
        raise RequestError.method_not_found("fs/write_text_file")

    async def read_text_file(self, path, session_id, **kwargs):
        raise RequestError.method_not_found("fs/read_text_file")

    async def create_terminal(self, command, session_id, **kwargs):
        raise RequestError.method_not_found("terminal/create")

    async def terminal_output(self, session_id, terminal_id, **kwargs):
        raise RequestError.method_not_found("terminal/output")

    async def release_terminal(self, session_id, terminal_id, **kwargs):
        raise RequestError.method_not_found("terminal/release")

    async def wait_for_terminal_exit(self, session_id, terminal_id, **kwargs):
        raise RequestError.method_not_found("terminal/wait_for_exit")

    async def kill_terminal(self, session_id, terminal_id, **kwargs):
        raise RequestError.method_not_found("terminal/kill")

    async def ext_method(self, method, params):
        raise RequestError.method_not_found(method)

    async def ext_notification(self, method, params):
        pass


async def main():
    host = "127.0.0.1"
    port = 9100
    errors = []

    print(f"[TEST] Connecting to {host}:{port}...")
    reader, writer = await asyncio.open_connection(host, port)
    client = MinimalClient()
    conn = connect_to_agent(client, writer, reader)

    # Test 1: Initialize
    print("[TEST] Sending initialize...")
    try:
        init_resp = await asyncio.wait_for(
            conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_capabilities=ClientCapabilities(),
                client_info=Implementation(
                    name="smoke-test", title="Smoke Test", version="0.1.0"
                ),
            ),
            timeout=10.0,
        )
        assert init_resp.agent_info is not None, "agent_info is None"
        assert init_resp.agent_info.name == "sancho-acp", (
            f"Expected 'sancho-acp', got '{init_resp.agent_info.name}'"
        )
        print(f"[TEST] ✅ Initialize OK — agent: {init_resp.agent_info.name} v{init_resp.agent_info.version}")
    except Exception as exc:
        errors.append(f"Initialize failed: {exc}")
        print(f"[TEST] ❌ Initialize FAILED: {exc}")

    # Test 2: New session
    print("[TEST] Sending new_session...")
    try:
        session = await asyncio.wait_for(
            conn.new_session(cwd="/tmp", mcp_servers=[]),
            timeout=15.0,
        )
        assert session.session_id is not None, "session_id is None"
        assert len(session.session_id) > 0, "session_id is empty"
        print(f"[TEST] ✅ New session OK — id: {session.session_id}")
    except Exception as exc:
        errors.append(f"New session failed: {exc}")
        print(f"[TEST] ❌ New session FAILED: {exc}")

    # Cleanup
    writer.close()
    await writer.wait_closed()

    if errors:
        print(f"\n[TEST] ❌ {len(errors)} error(s) found:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\n[TEST] ✅ All smoke tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
