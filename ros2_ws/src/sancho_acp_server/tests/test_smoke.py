"""Non-interactive smoke test: validates full ACP protocol handshake.

Tests: initialize, authenticate, new_session, set_session_mode,
ext_method, and close_session in sequence without requiring MCP server.
"""

from __future__ import annotations

import asyncio
import sys

from acp import PROTOCOL_VERSION, connect_to_agent, Client, RequestError
from acp.schema import (
    ClientCapabilities,
    Implementation,
)


class MinimalClient(Client):
    """Stub client that logs updates."""

    async def session_update(self, session_id, update, **kwargs):
        pass

    async def request_permission(self, options, session_id, tool_call, **kwargs):
        from acp.schema import DeniedOutcome
        return RequestError.method_not_found("permission")

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
        assert init_resp.agent_info.name == "sancho-acp-server", (
            f"Expected 'sancho-acp-server', got '{init_resp.agent_info.name}'"
        )
        print(f"[TEST] ✅ Initialize OK — agent: {init_resp.agent_info.name} v{init_resp.agent_info.version}")
    except Exception as exc:
        errors.append(f"Initialize failed: {exc}")
        print(f"[TEST] ❌ Initialize FAILED: {exc}")
        writer.close()
        await writer.wait_closed()
        sys.exit(1)

    # Test 2: Authenticate
    print("[TEST] Sending authenticate...")
    try:
        auth_resp = await asyncio.wait_for(
            conn.authenticate(method_id="basic"),
            timeout=10.0,
        )
        assert auth_resp is not None, "authenticate returned None"
        print(f"[TEST] ✅ Authenticate OK")
    except Exception as exc:
        errors.append(f"Authenticate failed: {exc}")
        print(f"[TEST] ❌ Authenticate FAILED: {exc}")

    # Test 3: New session
    print("[TEST] Sending new_session...")
    try:
        session = await asyncio.wait_for(
            conn.new_session(cwd="/tmp", mcp_servers=[]),
            timeout=15.0,
        )
        assert session.session_id is not None, "session_id is None"
        assert len(session.session_id) > 0, "session_id is empty"
        session_id = session.session_id
        print(f"[TEST] ✅ New session OK — id: {session_id}")
    except Exception as exc:
        errors.append(f"New session failed: {exc}")
        print(f"[TEST] ❌ New session FAILED: {exc}")
        writer.close()
        await writer.wait_closed()
        sys.exit(1)

    # Test 4: set_session_mode
    print(f"[TEST] Sending set_session_mode for {session_id}...")
    try:
        mode_resp = await asyncio.wait_for(
            conn.set_session_mode(mode_id="default", session_id=session_id),
            timeout=10.0,
        )
        assert mode_resp is not None, "set_session_mode returned None"
        print(f"[TEST] ✅ set_session_mode OK")
    except Exception as exc:
        errors.append(f"set_session_mode failed: {exc}")
        print(f"[TEST] ❌ set_session_mode FAILED: {exc}")

    # Test 5: ext_method
    print("[TEST] Sending ext_method...")
    try:
        ext_resp = await asyncio.wait_for(
            conn.ext_method(method="ping", params={}),
            timeout=10.0,
        )
        assert ext_resp is not None, "ext_method returned None"
        print(f"[TEST] ✅ ext_method OK")
    except Exception as exc:
        errors.append(f"ext_method failed: {exc}")
        print(f"[TEST] ❌ ext_method FAILED: {exc}")

    # Test 6: close_session
    print(f"[TEST] Sending close_session for {session_id}...")
    try:
        close_resp = await asyncio.wait_for(
            conn.close_session(session_id=session_id),
            timeout=10.0,
        )
        assert close_resp is not None, "close_session returned None"
        print(f"[TEST] ✅ close_session OK")
    except Exception as exc:
        errors.append(f"close_session failed: {exc}")
        print(f"[TEST] ❌ close_session FAILED: {exc}")

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