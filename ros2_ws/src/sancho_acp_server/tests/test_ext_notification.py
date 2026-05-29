"""Test ACP extension notifications.

Verifies that ext_notification is handled correctly (no response expected).
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

    print(f"[TEST] Connecting to {host}:{port}...")
    reader, writer = await asyncio.open_connection(host, port)
    client = MinimalClient()
    conn = connect_to_agent(client, writer, reader)

    # Initialize
    print("[TEST] Sending initialize...")
    try:
        init_resp = await asyncio.wait_for(
            conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_capabilities=ClientCapabilities(),
                client_info=Implementation(
                    name="notif-test", title="Notification Test", version="0.1.0"
                ),
            ),
            timeout=10.0,
        )
        print(f"[TEST] ✅ Initialize OK")
    except Exception as exc:
        print(f"[TEST] ❌ Initialize FAILED: {exc}")
        writer.close()
        await writer.wait_closed()
        sys.exit(1)

    # ext_notification does not expect a response, so we just verify
    # it does not raise an error by sending one.
    print("[TEST] Sending ext_notification (no response expected)...")
    try:
        await conn.ext_notification(method="client_event", params={"type": "test"})
        print("[TEST] ✅ ext_notification sent without error")
    except Exception as exc:
        print(f"[TEST] ❌ ext_notification FAILED: {exc}")
        sys.exit(1)

    writer.close()
    await writer.wait_closed()
    print("\n[TEST] ✅ ext_notification test passed!")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())