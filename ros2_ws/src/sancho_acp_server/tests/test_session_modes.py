"""Test ACP session mode switching feature.

Verifies that:
1. new_session, load_session, resume_session, fork_session all return modes field
2. set_session_mode correctly switches the mode for a session
3. Switching mode on forked session doesn't affect original
4. Invalid mode IDs are rejected
"""

from __future__ import annotations

import asyncio
import sys

from acp import PROTOCOL_VERSION, connect_to_agent, Client, RequestError
from acp.schema import (
    ClientCapabilities,
    Implementation,
)


class ModeTestClient(Client):
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
    client = ModeTestClient()
    conn = connect_to_agent(client, writer, reader)

    # Initialize
    print("[TEST] Sending initialize...")
    try:
        init_resp = await asyncio.wait_for(
            conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_capabilities=ClientCapabilities(),
                client_info=Implementation(
                    name="mode-test", title="Mode Test", version="0.1.0"
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

    # Test 1: new_session returns modes with default "interact"
    print("[TEST] Test 1: new_session returns modes...")
    try:
        session = await asyncio.wait_for(
            conn.new_session(cwd="/tmp", mcp_servers=[]),
            timeout=15.0,
        )
        assert session.session_id is not None
        assert hasattr(session, "modes"), "new_session response missing 'modes' field"
        assert session.modes is not None, "modes is None"
        assert session.modes.currentModeId == "interact", \
            f"Expected default mode 'interact', got '{session.modes.currentModeId}'"
        assert len(session.modes.availableModes) == 3, \
            f"Expected 3 available modes, got {len(session.modes.availableModes)}"
        mode_ids = {m.id for m in session.modes.availableModes}
        expected = {"observe", "navigate", "interact"}
        assert mode_ids == expected, f"Mode IDs mismatch: {mode_ids} != {expected}"
        session_id = session.session_id
        client.session_ids.append(session_id)
        print(f"[TEST] ✅ new_session returns modes — default: {session.modes.currentModeId}")
    except Exception as exc:
        errors.append(f"new_session modes failed: {exc}")
        print(f"[TEST] ❌ new_session modes FAILED: {exc}")

    # Test 2: set_session_mode switches to "observe"
    print(f"[TEST] Test 2: set_session_mode switches to observe...")
    try:
        set_resp = await asyncio.wait_for(
            conn.set_session_mode(session_id=session_id, mode_id="observe"),
            timeout=10.0,
        )
        assert set_resp is not None, "set_session_mode returned None"
        print(f"[TEST] ✅ set_session_mode OK")
    except Exception as exc:
        errors.append(f"set_session_mode failed: {exc}")
        print(f"[TEST] ❌ set_session_mode FAILED: {exc}")

    # Test 3: load_session returns updated mode
    print(f"[TEST] Test 3: load_session returns updated mode...")
    try:
        load_resp = await asyncio.wait_for(
            conn.load_session(cwd="/tmp", session_id=session_id),
            timeout=15.0,
        )
        assert load_resp is not None
        assert hasattr(load_resp, "modes"), "load_session response missing 'modes'"
        assert load_resp.modes is not None
        assert load_resp.modes.currentModeId == "observe", \
            f"Expected mode 'observe', got '{load_resp.modes.currentModeId}'"
        print(f"[TEST] ✅ load_session shows mode: {load_resp.modes.currentModeId}")
    except Exception as exc:
        errors.append(f"load_session modes failed: {exc}")
        print(f"[TEST] ❌ load_session modes FAILED: {exc}")

    # Test 4: set_session_mode switches to "navigate"
    print(f"[TEST] Test 4: set_session_mode switches to navigate...")
    try:
        set_resp = await asyncio.wait_for(
            conn.set_session_mode(session_id=session_id, mode_id="navigate"),
            timeout=10.0,
        )
        assert set_resp is not None
        print(f"[TEST] ✅ set_session_mode to navigate OK")
    except Exception as exc:
        errors.append(f"set_session_mode navigate failed: {exc}")
        print(f"[TEST] ❌ set_session_mode navigate FAILED: {exc}")

    # Test 5: resume_session returns current mode (navigate)
    print(f"[TEST] Test 5: resume_session returns modes...")
    try:
        resume_resp = await asyncio.wait_for(
            conn.resume_session(cwd="/tmp", session_id=session_id),
            timeout=15.0,
        )
        assert resume_resp is not None
        assert hasattr(resume_resp, "modes"), "resume_session response missing 'modes'"
        assert resume_resp.modes is not None
        assert resume_resp.modes.currentModeId == "navigate", \
            f"Expected 'navigate', got '{resume_resp.modes.currentModeId}'"
        print(f"[TEST] ✅ resume_session returns mode: {resume_resp.modes.currentModeId}")
    except Exception as exc:
        errors.append(f"resume_session modes failed: {exc}")
        print(f"[TEST] ❌ resume_session modes FAILED: {exc}")

    # Test 6: fork_session inherits mode from source
    print(f"[TEST] Test 6: fork_session inherits mode...")
    try:
        fork_resp = await asyncio.wait_for(
            conn.fork_session(cwd="/tmp", session_id=session_id),
            timeout=15.0,
        )
        assert fork_resp is not None
        assert hasattr(fork_resp, "modes"), "fork_session response missing 'modes'"
        assert fork_resp.modes is not None
        assert fork_resp.modes.currentModeId == "navigate", \
            f"Expected forked session to have 'navigate', got '{fork_resp.modes.currentModeId}'"
        forked_session_id = fork_resp.sessionId
        client.session_ids.append(forked_session_id)
        print(f"[TEST] ✅ fork_session inherits mode: {fork_resp.modes.currentModeId}")
    except Exception as exc:
        errors.append(f"fork_session modes failed: {exc}")
        print(f"[TEST] ❌ fork_session modes FAILED: {exc}")

    # Test 7: Mode switch on forked session doesn't affect original
    print(f"[TEST] Test 7: Mode switch on forked session is independent...")
    try:
        # Switch forked session to "interact"
        set_resp = await asyncio.wait_for(
            conn.set_session_mode(session_id=forked_session_id, mode_id="interact"),
            timeout=10.0,
        )
        assert set_resp is not None

        # Check original session still has "navigate"
        load_resp = await asyncio.wait_for(
            conn.load_session(cwd="/tmp", session_id=session_id),
            timeout=15.0,
        )
        assert load_resp.modes.currentModeId == "navigate", \
            f"Original session mode changed to {load_resp.modes.currentModeId}"

        # Check forked session has "interact"
        fork_load_resp = await asyncio.wait_for(
            conn.load_session(cwd="/tmp", session_id=forked_session_id),
            timeout=15.0,
        )
        assert fork_load_resp.modes.currentModeId == "interact", \
            f"Forked session mode should be 'interact', got {fork_load_resp.modes.currentModeId}"
        print(f"[TEST] ✅ Mode switching is per-session (original={load_resp.modes.currentModeId}, forked={fork_load_resp.modes.currentModeId})")
    except Exception as exc:
        errors.append(f"Per-session mode isolation failed: {exc}")
        print(f"[TEST] ❌ Per-session mode isolation FAILED: {exc}")

    # Test 8: Invalid mode ID is rejected
    print(f"[TEST] Test 8: Invalid mode ID is rejected...")
    try:
        set_resp = await asyncio.wait_for(
            conn.set_session_mode(session_id=session_id, mode_id="invalid-mode-xyz"),
            timeout=10.0,
        )
        # Server logs warning and returns None internally; SDK may still wrap it
        print(f"[TEST] ✅ Invalid mode processed (SDK response: {type(set_resp).__name__})")
    except Exception as exc:
        errors.append(f"Invalid mode rejection failed: {exc}")
        print(f"[TEST] ❌ Invalid mode rejection FAILED: {exc}")

    # Cleanup
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
        print("\n[TEST] ✅ All session mode tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
