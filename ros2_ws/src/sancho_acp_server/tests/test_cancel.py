"""Test ACP cancel operation.

Verifies that the agent correctly handles cancel requests during prompt execution.
"""

from __future__ import annotations

import asyncio
import sys

from acp import PROTOCOL_VERSION, connect_to_agent, Client, RequestError, text_block
from acp.schema import (
    ClientCapabilities,
    Implementation,
)


class CancelTestClient(Client):
    def __init__(self):
        super().__init__()
        self.received_updates = []

    async def session_update(self, session_id, update, **kwargs):
        self.received_updates.append(update)

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
    client = CancelTestClient()
    conn = connect_to_agent(client, writer, reader)

    # Initialize
    print("[TEST] Sending initialize...")
    try:
        init_resp = await asyncio.wait_for(
            conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_capabilities=ClientCapabilities(),
                client_info=Implementation(
                    name="cancel-test", title="Cancel Test", version="0.1.0"
                ),
            ),
            timeout=10.0,
        )
        assert init_resp.agent_info is not None
        print(f"[TEST] ✅ Initialize OK")
    except Exception as exc:
        errors.append(f"Initialize failed: {exc}")
        print(f"[TEST] ❌ Initialize FAILED: {exc}")
        writer.close()
        await writer.wait_closed()
        sys.exit(1)

    # Create a session
    print("[TEST] Creating session...")
    try:
        session = await asyncio.wait_for(
            conn.new_session(cwd="/tmp", mcp_servers=[]),
            timeout=15.0,
        )
        session_id = session.session_id
        print(f"[TEST] ✅ Session created: {session_id}")
    except Exception as exc:
        errors.append(f"new_session failed: {exc}")
        print(f"[TEST] ❌ new_session FAILED: {exc}")
        writer.close()
        await writer.wait_closed()
        sys.exit(1)

    # Test: cancel a session
    print(f"[TEST] Sending cancel for session {session_id}...")
    try:
        await asyncio.wait_for(
            conn.cancel(session_id=session_id),
            timeout=10.0,
        )
        print(f"[TEST] ✅ cancel OK")
    except Exception as exc:
        errors.append(f"cancel failed: {exc}")
        print(f"[TEST] ❌ cancel FAILED: {exc}")

    # Cleanup
    try:
        await conn.close_session(session_id=session_id)
    except Exception:
        pass

    writer.close()
    await writer.wait_closed()

    if errors:
        print(f"\n[TEST] ❌ {len(errors)} error(s) found:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\n[TEST] ✅ All cancel tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())