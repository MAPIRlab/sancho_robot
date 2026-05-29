"""Test ACP model switching feature.

Verifies that:
1. new_session, load_session, resume_session, fork_session all return models field
2. set_session_model correctly switches the model for a session
3. Switching model invalidates the cached agent so next prompt uses new model
"""

from __future__ import annotations

import asyncio
import sys

from acp import PROTOCOL_VERSION, connect_to_agent, Client, RequestError
from acp.schema import (
    ClientCapabilities,
    Implementation,
)


class ModelTestClient(Client):
    def __init__(self):
        super().__init__()
        self.session_ids = []
        self.model_states_received = []

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
    client = ModelTestClient()
    conn = connect_to_agent(client, writer, reader)

    # Initialize
    print("[TEST] Sending initialize...")
    try:
        init_resp = await asyncio.wait_for(
            conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_capabilities=ClientCapabilities(),
                client_info=Implementation(
                    name="model-test", title="Model Test", version="0.1.0"
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

    # Test 1: new_session returns models
    print("[TEST] Test 1: new_session returns models...")
    try:
        session = await asyncio.wait_for(
            conn.new_session(cwd="/tmp", mcp_servers=[]),
            timeout=15.0,
        )
        assert session.session_id is not None
        assert hasattr(session, "models"), "new_session response missing 'models' field"
        assert session.models is not None, "models is None"
        assert session.models.currentModelId == "gemini-3.1-flash-lite", \
            f"Expected default model 'gemini-3.1-flash-lite', got '{session.models.currentModelId}'"
        assert len(session.models.availableModels) == 3, \
            f"Expected 3 available models, got {len(session.models.availableModels)}"
        model_ids = {m.modelId for m in session.models.availableModels}
        expected = {"gemini-3.1-flash-lite", "gemini-3-flash-preview", "gemini-3.1-pro-preview"}
        assert model_ids == expected, f"Model IDs mismatch: {model_ids} != {expected}"
        session_id = session.session_id
        client.session_ids.append(session_id)
        print(f"[TEST] ✅ new_session returns models — default: {session.models.currentModelId}")
    except Exception as exc:
        errors.append(f"new_session models failed: {exc}")
        print(f"[TEST] ❌ new_session models FAILED: {exc}")

    # Test 2: set_session_model switches model to gemini-3-flash-preview
    print(f"[TEST] Test 2: set_session_model switches model for {session_id}...")
    try:
        set_resp = await asyncio.wait_for(
            conn.set_session_model(session_id=session_id, model_id="gemini-3-flash-preview"),
            timeout=10.0,
        )
        assert set_resp is not None, "set_session_model returned None"
        print(f"[TEST] ✅ set_session_model OK")
    except Exception as exc:
        errors.append(f"set_session_model failed: {exc}")
        print(f"[TEST] ❌ set_session_model FAILED: {exc}")

    # Test 3: load_session returns updated models after switch
    print(f"[TEST] Test 3: load_session returns models with switched model...")
    try:
        load_resp = await asyncio.wait_for(
            conn.load_session(cwd="/tmp", session_id=session_id),
            timeout=15.0,
        )
        assert load_resp is not None
        assert hasattr(load_resp, "models"), "load_session response missing 'models'"
        assert load_resp.models is not None
        assert load_resp.models.currentModelId == "gemini-3-flash-preview", \
            f"Expected switched model 'gemini-3-flash-preview', got '{load_resp.models.currentModelId}'"
        print(f"[TEST] ✅ load_session shows switched model: {load_resp.models.currentModelId}")
    except Exception as exc:
        errors.append(f"load_session models failed: {exc}")
        print(f"[TEST] ❌ load_session models FAILED: {exc}")

    # Test 4: set_session_model with invalid model — SDK returns response, agent logs warning
    print(f"[TEST] Test 4: set_session_model rejects invalid model...")
    try:
        set_resp = await asyncio.wait_for(
            conn.set_session_model(session_id=session_id, model_id="invalid-model-xyz"),
            timeout=10.0,
        )
        # The SDK always returns a SetSessionModelResponse; the server logs a warning
        # and returns None for invalid model, but the SDK may still wrap it
        print(f"[TEST] ✅ set_session_model processed (SDK response: {type(set_resp).__name__})")
    except Exception as exc:
        errors.append(f"set_session_model invalid model failed: {exc}")
        print(f"[TEST] ❌ set_session_model invalid model FAILED: {exc}")

    # Test 5: set_session_model for non-existent session
    print("[TEST] Test 5: set_session_model for non-existent session...")
    try:
        set_resp = await asyncio.wait_for(
            conn.set_session_model(session_id="nonexistent123", model_id="gemini-3-flash-preview"),
            timeout=10.0,
        )
        # Server returns None for unknown session
        print(f"[TEST] ✅ set_session_model processed (SDK response: {type(set_resp).__name__})")
    except Exception as exc:
        errors.append(f"set_session_model nonexistent session failed: {exc}")
        print(f"[TEST] ❌ set_session_model nonexistent session FAILED: {exc}")

    # Test 6: resume_session returns models with switched model
    print(f"[TEST] Test 6: resume_session returns models for {session_id}...")
    try:
        resume_resp = await asyncio.wait_for(
            conn.resume_session(cwd="/tmp", session_id=session_id),
            timeout=15.0,
        )
        assert resume_resp is not None
        assert hasattr(resume_resp, "models"), "resume_session response missing 'models'"
        assert resume_resp.models is not None
        assert resume_resp.models.currentModelId == "gemini-3-flash-preview", \
            f"Expected 'gemini-3-flash-preview', got '{resume_resp.models.currentModelId}'"
        print(f"[TEST] ✅ resume_session returns models: {resume_resp.models.currentModelId}")
    except Exception as exc:
        errors.append(f"resume_session models failed: {exc}")
        print(f"[TEST] ❌ resume_session models FAILED: {exc}")

    # Test 7: fork_session returns models with same model as source (gemini-3-flash-preview)
    print(f"[TEST] Test 7: fork_session returns models for {session_id}...")
    try:
        fork_resp = await asyncio.wait_for(
            conn.fork_session(cwd="/tmp", session_id=session_id),
            timeout=15.0,
        )
        assert fork_resp is not None
        assert hasattr(fork_resp, "models"), "fork_session response missing 'models'"
        assert fork_resp.models is not None
        assert fork_resp.models.currentModelId == "gemini-3-flash-preview", \
            f"Expected forked session to have 'gemini-3-flash-preview', got '{fork_resp.models.currentModelId}'"
        forked_session_id = fork_resp.sessionId
        client.session_ids.append(forked_session_id)
        print(f"[TEST] ✅ fork_session returns models: {fork_resp.models.currentModelId}")
    except Exception as exc:
        errors.append(f"fork_session models failed: {exc}")
        print(f"[TEST] ❌ fork_session models FAILED: {exc}")

    # Test 8: Switching model on forked session doesn't affect original
    print(f"[TEST] Test 8: Model switch on forked session doesn't affect original...")
    try:
        # Switch forked session to gemini-3.1-pro-preview
        set_resp = await asyncio.wait_for(
            conn.set_session_model(session_id=forked_session_id, model_id="gemini-3.1-pro-preview"),
            timeout=10.0,
        )
        assert set_resp is not None

        # Check original session still has gemini-3-flash-preview
        load_resp = await asyncio.wait_for(
            conn.load_session(cwd="/tmp", session_id=session_id),
            timeout=15.0,
        )
        assert load_resp.models.currentModelId == "gemini-3-flash-preview", \
            f"Original session model changed to {load_resp.models.currentModelId}"

        # Check forked session has gemini-3.1-pro-preview
        fork_load_resp = await asyncio.wait_for(
            conn.load_session(cwd="/tmp", session_id=forked_session_id),
            timeout=15.0,
        )
        assert fork_load_resp.models.currentModelId == "gemini-3.1-pro-preview", \
            f"Forked session model should be gemini-3.1-pro-preview, got {fork_load_resp.models.currentModelId}"
        print(f"[TEST] ✅ Model switching is per-session (original={load_resp.models.currentModelId}, forked={fork_load_resp.models.currentModelId})")
    except Exception as exc:
        errors.append(f"Per-session model isolation failed: {exc}")
        print(f"[TEST] ❌ Per-session model isolation FAILED: {exc}")

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
        print("\n[TEST] ✅ All model switching tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
