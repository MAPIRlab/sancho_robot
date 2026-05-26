"""Quick smoke-test client for the Sancho ACP TCP server.

Connects via TCP, sends initialize + new_session + a simple prompt,
and prints all session updates received from the agent.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from acp import (
    PROTOCOL_VERSION,
    connect_to_agent,
    text_block,
    Client,
    RequestError,
)
from acp.schema import (
    AgentMessageChunk,
    AgentThoughtChunk,
    AvailableCommandsUpdate,
    ClientCapabilities,
    ConfigOptionUpdate,
    CreateTerminalResponse,
    CurrentModeUpdate,
    EnvVariable,
    Implementation,
    KillTerminalResponse,
    PermissionOption,
    ReadTextFileResponse,
    ReleaseTerminalResponse,
    RequestPermissionResponse,
    SessionInfoUpdate,
    TerminalOutputResponse,
    TextContentBlock,
    ToolCallProgress,
    ToolCallStart,
    ToolCallUpdate,
    UsageUpdate,
    UserMessageChunk,
    WaitForTerminalExitResponse,
    WriteTextFileResponse,
    AllowedOutcome,
)


class TestClient(Client):
    """Minimal ACP client that prints all session updates."""

    async def session_update(self, session_id, update, **kwargs):
        if isinstance(update, AgentMessageChunk):
            content = update.content
            if isinstance(content, TextContentBlock):
                print(f"  📨 Agent: {content.text}")
            elif isinstance(content, dict):
                print(f"  📨 Agent: {content.get('text', content)}")
            else:
                print(f"  📨 Agent: {content}")
        elif isinstance(update, AgentThoughtChunk):
            content = update.content
            if isinstance(content, TextContentBlock):
                print(f"  💭 Thought: {content.text}")
            elif isinstance(content, dict):
                print(f"  💭 Thought: {content.get('text', content)}")
            else:
                print(f"  💭 Thought: {content}")
        elif isinstance(update, ToolCallStart):
            print(f"  🔧 Tool start: {update.title}")
        elif isinstance(update, ToolCallProgress):
            print(f"  🔧 Tool progress: {update.tool_call_id}")
        else:
            print(f"  ℹ️  Update: {type(update).__name__}")

    async def request_permission(self, options, session_id, tool_call, **kwargs):
        print(f"  🔐 Permission requested for: {tool_call.title}")
        # Auto-approve for testing
        if options:
            return RequestPermissionResponse(
                outcome=AllowedOutcome(
                    option_id=options[0].option_id, outcome="selected"
                )
            )
        from acp.schema import DeniedOutcome
        return RequestPermissionResponse(
            outcome=DeniedOutcome(outcome="cancelled")
        )

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
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9100

    print(f"Connecting to Sancho ACP server at {host}:{port}...")

    reader, writer = await asyncio.open_connection(host, port)
    client = TestClient()
    conn = connect_to_agent(client, writer, reader)

    # 1. Initialize
    print("\n--- Initialize ---")
    init_resp = await conn.initialize(
        protocol_version=PROTOCOL_VERSION,
        client_capabilities=ClientCapabilities(),
        client_info=Implementation(
            name="test-client", title="Test Client", version="0.1.0"
        ),
    )
    print(f"  ✅ Connected to: {init_resp.agent_info.name} v{init_resp.agent_info.version}")
    print(f"  Protocol version: {init_resp.protocol_version}")

    # 2. New session
    print("\n--- New Session ---")
    session = await conn.new_session(cwd="/tmp", mcp_servers=[])
    print(f"  ✅ Session ID: {session.session_id}")

    # 3. Interactive prompt loop
    print("\n--- Interactive Mode ---")
    print("Type a message (or 'exit' to quit):\n")

    loop = asyncio.get_running_loop()
    while True:
        try:
            line = await loop.run_in_executor(
                None, lambda: input("> ").strip()
            )
        except (EOFError, KeyboardInterrupt):
            break

        if not line:
            continue
        if line.lower() in {"exit", "quit"}:
            break
        if line.lower() == ":cancel":
            await conn.cancel(session_id=session.session_id)
            print("  ⚡ Cancel sent.")
            continue

        try:
            resp = await conn.prompt(
                session_id=session.session_id,
                prompt=[text_block(line)],
            )
            print(f"  ✅ Prompt completed: {resp.stop_reason}")
        except Exception as exc:
            print(f"  ❌ Error: {exc}")

    # Cleanup
    writer.close()
    await writer.wait_closed()
    print("\nDisconnected.")


if __name__ == "__main__":
    asyncio.run(main())
