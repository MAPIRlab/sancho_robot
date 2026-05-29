"""Test ACP session management operations.

Covers: new_session, load_session, list_sessions, fork_session,
resume_session, close_session.
"""

from __future__ import annotations

import asyncio
import sys
from uuid import uuid4

from acp import PROTOCOL_VERSION, connect_to_agent, Client, RequestError
from acp.schema import (
    ClientCapabilities,
    Implementation,
)


class SessionTestClient(Client):
    def __init__(self):
        super().__init__()
        self.session_ids = []

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
    client = SessionTestClient()
    conn = connect_to_agent(client, writer, reader)

    # Initialize
    print("[TEST] Sending initialize...")
    try:
        init_resp = await asyncio.wait_for(
            conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_capabilities=ClientCapabilities(),
                client_info=Implementation(
                    name="session-test", title="Session Test", version="0.1.0"
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

    # Test 1: new_session
    print("[TEST] Sending new_session...")
    try:
        session = await asyncio.wait_for(
            conn.new_session(cwd="/tmp", mcp_servers=[]),
            timeout=15.0,
        )
        assert session.session_id is not None and len(session.session_id) > 0
        client.session_ids.append(session.session_id)
        print(f"[TEST] ✅ new_session OK — id: {session.session_id}")
    except Exception as exc:
        errors.append(f"new_session failed: {exc}")
        print(f"[TEST] ❌ new_session FAILED: {exc}")

    # Test 2: list_sessions
    print("[TEST] Sending list_sessions...")
    try:
        list_resp = await asyncio.wait_for(
            conn.list_sessions(cwd="/tmp"),
            timeout=10.0,
        )
        assert list_resp.sessions is not None
        found = any(s.sessionId == client.session_ids[0] for s in list_resp.sessions)
        assert found, f"Session {client.session_ids[0]} not found in list"
        print(f"[TEST] ✅ list_sessions OK — {len(list_resp.sessions)} session(s) found")
    except Exception as exc:
        errors.append(f"list_sessions failed: {exc}")
        print(f"[TEST] ❌ list_sessions FAILED: {exc}")

    # Test 3: load_session (existing session)
    print(f"[TEST] Sending load_session for {client.session_ids[0]}...")
    try:
        load_resp = await asyncio.wait_for(
            conn.load_session(cwd="/tmp", session_id=client.session_ids[0]),
            timeout=15.0,
        )
        assert load_resp is not None
        print(f"[TEST] ✅ load_session OK (existing session)")
    except Exception as exc:
        errors.append(f"load_session failed: {exc}")
        print(f"[TEST] ❌ load_session FAILED: {exc}")

    # Test 4: load_session (new session id — creates automatically)
    new_id = uuid4().hex
    print(f"[TEST] Sending load_session for new id {new_id}...")
    try:
        load_resp = await asyncio.wait_for(
            conn.load_session(cwd="/tmp", session_id=new_id),
            timeout=15.0,
        )
        assert load_resp is not None
        client.session_ids.append(new_id)
        print(f"[TEST] ✅ load_session OK (created new session)")
    except Exception as exc:
        errors.append(f"load_session (new) failed: {exc}")
        print(f"[TEST] ❌ load_session (new) FAILED: {exc}")

    # Test 5: fork_session
    print(f"[TEST] Sending fork_session from {client.session_ids[0]}...")
    try:
        fork_resp = await asyncio.wait_for(
            conn.fork_session(cwd="/tmp", session_id=client.session_ids[0]),
            timeout=15.0,
        )
        assert fork_resp.sessionId is not None and fork_resp.sessionId != client.session_ids[0]
        client.session_ids.append(fork_resp.sessionId)
        print(f"[TEST] ✅ fork_session OK — new id: {fork_resp.sessionId}")
    except Exception as exc:
        errors.append(f"fork_session failed: {exc}")
        print(f"[TEST] ❌ fork_session FAILED: {exc}")

    # Test 6: resume_session
    print(f"[TEST] Sending resume_session for {client.session_ids[1]}...")
    try:
        resume_resp = await asyncio.wait_for(
            conn.resume_session(cwd="/tmp", session_id=client.session_ids[1]),
            timeout=15.0,
        )
        assert resume_resp is not None
        print(f"[TEST] ✅ resume_session OK")
    except Exception as exc:
        errors.append(f"resume_session failed: {exc}")
        print(f"[TEST] ❌ resume_session FAILED: {exc}")

    # Test 7: close_session
    session_to_close = client.session_ids[-1]
    print(f"[TEST] Sending close_session for {session_to_close}...")
    try:
        close_resp = await asyncio.wait_for(
            conn.close_session(session_id=session_to_close),
            timeout=10.0,
        )
        assert close_resp is not None
        client.session_ids.remove(session_to_close)
        print(f"[TEST] ✅ close_session OK")
    except Exception as exc:
        errors.append(f"close_session failed: {exc}")
        print(f"[TEST] ❌ close_session FAILED: {exc}")

    # Cleanup remaining sessions
    for sid in list(client.session_ids):
        print(f"[TEST] Cleaning up session {sid}...")
        try:
            await conn.close_session(session_id=sid)
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
        print("\n[TEST] ✅ All session management tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())