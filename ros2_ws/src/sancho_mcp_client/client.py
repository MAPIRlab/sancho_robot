from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
import socket
from google.oauth2 import service_account
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.sessions import create_session
from langchain_mcp_adapters.tools import load_mcp_tools

# Force IPv4 to avoid IPv6 "Network is unreachable" errors
orig_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = getaddrinfo_ipv4


# Silence langchain_google_genai schema warnings
logging.getLogger("langchain_google_genai._function_utils").setLevel(logging.ERROR)

DEFAULT_PROMPT_PATH = Path(__file__).resolve().parent / "SYSTEM_PROMPT.md"


def load_system_prompt() -> str:
    prompt_path = Path(
        os.environ.get("SANCHO_SYSTEM_PROMPT_PATH", str(DEFAULT_PROMPT_PATH))
    )
    if not prompt_path.exists():
        return "You are controlling Sancho, a mobile robot. Use the MCP tools."
    return prompt_path.read_text(encoding="utf-8")


def _format_ai_message(content: Any) -> str:
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    parts.append(str(part.get("text", "")))
                elif part.get("type") == "image_url":
                    parts.append("[image]")
        return "\n".join(p for p in parts if p)
    return str(content)


def _summarize_tool_output(output: Any) -> str:
    if isinstance(output, list):
        for part in output:
            if isinstance(part, dict) and part.get("type") == "image_url":
                return "<image payload>"
        return str(output)
    if isinstance(output, dict):
        if output.get("type") == "image":
            data_len = len(str(output.get("data", "")))
            return f"<image payload bytes={data_len}>"
        if "error" in output:
            return f"error: {output['error']}"
    text = str(output)
    return text if len(text) <= 500 else f"{text[:500]}..."


class ToolLogger(BaseCallbackHandler):
    def on_tool_start(self, serialized: dict, input_str: str, **kwargs) -> None:
        name = serialized.get("name", "tool")
        print(f"[tool:start] {name} <- {input_str}")

    def on_tool_end(self, output: Any, **kwargs) -> None:
        name = kwargs.get("name", "tool")
        print(f"[tool:end] {name} -> {_summarize_tool_output(output)}")


async def _call_tool(tool: Any, args: dict) -> Any:
    if hasattr(tool, "ainvoke"):
        return await tool.ainvoke(args)
    return await asyncio.to_thread(tool.invoke, args)


def _mcp_image_payload_to_content(payload: Any) -> Any:
    # Handle list of blocks (from langchain-mcp-adapters)
    if isinstance(payload, list):
        new_blocks = []
        for block in payload:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                try:
                    data = json.loads(text)
                    if isinstance(data, dict) and data.get("type") == "image":
                        new_blocks.extend(_create_multimodal_content(data))
                        continue
                except json.JSONDecodeError:
                    pass
            new_blocks.append(block)
        return new_blocks

    # Handle direct string
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
            if isinstance(data, dict) and data.get("type") == "image":
                return _create_multimodal_content(data)
        except json.JSONDecodeError:
            pass

    # Handle direct dict
    if isinstance(payload, dict) and payload.get("type") == "image":
        return _create_multimodal_content(payload)

    return payload


def _create_multimodal_content(data: dict) -> list[dict]:
    b64_data = data.get("data")
    if not b64_data:
        return [{"type": "text", "text": "error: Empty image payload"}]
    mime = data.get("mime_type") or data.get("mimeType") or "image/jpeg"
    data_url = f"data:{mime};base64,{b64_data}"
    return [
        {"type": "text", "text": "Captured image from robot camera."},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]


def _wrap_take_photo(tools: list[Any]) -> list[Any]:
    tool_map = {tool.name: tool for tool in tools}
    raw_tool = tool_map.get("take_photo")
    if raw_tool is None:
        return tools

    async def _take_photo() -> Any:
        payload = await _call_tool(raw_tool, {})
        return _mcp_image_payload_to_content(payload)

    wrapped = StructuredTool.from_function(
        name="take_photo",
        description=raw_tool.description
        or "Capture a camera frame as an image payload.",
        coroutine=_take_photo,
    )

    return [tool for tool in tools if tool.name != "take_photo"] + [wrapped]


def _serialize_tools(tools: list[Any]) -> list[Any]:
    """Wraps all tools in a shared asyncio.Lock to execute them sequentially.
    This prevents concurrent execution issues over the streamable HTTP transport.
    """
    lock = asyncio.Lock()

    for tool in tools:
        original_coroutine = tool.coroutine
        original_func = tool.func

        # Use a closure to capture the original coroutine/func for each tool
        def make_serialized_coroutine(coro, func):
            async def serialized_coroutine(*args, **kwargs):
                async with lock:
                    if coro:
                        return await coro(*args, **kwargs)
                    else:
                        return await asyncio.to_thread(func, *args, **kwargs)
            return serialized_coroutine

        tool.coroutine = make_serialized_coroutine(original_coroutine, original_func)

    return tools



def _build_llm() -> ChatGoogleGenerativeAI:
    load_dotenv()

    # Locate and read service account credentials for Vertex AI
    env_path = os.environ.get("SANCHO_MCP_CREDENTIALS_PATH")
    if not env_path:
        raise RuntimeError("SANCHO_MCP_CREDENTIALS_PATH environment variable is not set in the environment or .env file.")

    credentials_path = Path(env_path)
    if not credentials_path.is_absolute():
        credentials_path = Path(__file__).resolve().parent / credentials_path

    if not credentials_path.exists():
        raise RuntimeError(f"Credentials file not found at {credentials_path}")

    try:
        with open(credentials_path, "r", encoding="utf-8") as f:
            credentials_data = json.load(f)
        project_id = credentials_data.get("project_id")
        if not project_id:
            raise RuntimeError("project_id missing in service account JSON.")
    except Exception as e:
        raise RuntimeError(f"Failed to read service account credentials: {e}")

    credentials = service_account.Credentials.from_service_account_file(
        str(credentials_path),
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    model = os.environ.get("SANCHO_MCP_LLM_MODEL", "gemini-3.1-flash-lite")
    temperature = float(os.environ.get("SANCHO_MCP_LLM_TEMPERATURE", "0.2"))

    return ChatGoogleGenerativeAI(
        model=model,
        project=project_id,
        credentials=credentials,
        vertexai=True,
        temperature=temperature,
    )


def _ensure_non_empty_ai_messages(messages: list[Any]) -> list[Any]:
    """Gemini API requires that every message in the conversation history has at least
    one non-empty part/content block. When using ReAct agents, LangGraph/LangChain
    might generate AIMessages with empty text content (e.g., when the agent only calls
    a tool). This function patches any empty AIMessage by adding a minimal text placeholder
    to prevent 400 Invalid Argument API crashes, without deleting history or losing context.
    """
    patched_messages = []
    for msg in messages:
        if not isinstance(msg, AIMessage):
            patched_messages.append(msg)
            continue

        has_text_or_media = False
        if isinstance(msg.content, str):
            has_text_or_media = bool(msg.content.strip())
        elif isinstance(msg.content, list):
            for part in msg.content:
                if isinstance(part, str) and part.strip():
                    has_text_or_media = True
                    break
                if isinstance(part, dict) and part.get("type") in {
                    "text",
                    "image",
                    "media",
                    "thinking",
                    "reasoning",
                }:
                    # If it's a text block, ensure the text itself is not empty
                    if part.get("type") == "text" and not str(part.get("text", "")).strip():
                        continue
                    has_text_or_media = True
                    break

        if not has_text_or_media:
            # Replace empty content with a minimal placeholder to satisfy Gemini's API schema
            if isinstance(msg.content, list):
                new_content = list(msg.content) + [{"type": "text", "text": "."}]
            else:
                new_content = "."
            msg = AIMessage(
                content=new_content,
                tool_calls=msg.tool_calls,
                additional_kwargs=msg.additional_kwargs,
                response_metadata=msg.response_metadata,
                id=msg.id,
            )
        patched_messages.append(msg)
    return patched_messages


async def chat_loop(agent: Any, system_prompt: str) -> None:
    messages: list[Any] = [SystemMessage(content=system_prompt)]
    callback = ToolLogger()

    print("Sancho MCP client ready. Type your request (or 'exit').")
    while True:
        user_input = await asyncio.to_thread(input, "> ")
        if not user_input:
            continue
        if user_input.strip().lower() in {"exit", "quit"}:
            break

        messages.append(HumanMessage(content=user_input))
        result = await agent.ainvoke(
            {"messages": messages},
            config={"callbacks": [callback]},
        )
        messages = _ensure_non_empty_ai_messages(result.get("messages", messages))
        reply = next(
            (msg for msg in reversed(messages) if isinstance(msg, AIMessage)), None
        )
        if reply is not None:
            print(f"Sancho> {_format_ai_message(reply.content)}")



async def main() -> None:
    server_url = os.environ.get("SANCHO_MCP_SERVER_URL", "http://127.0.0.1:8000/mcp")
    system_prompt = load_system_prompt()
    llm = _build_llm()

    connection = {"transport": "streamable_http", "url": server_url}
    async with create_session(connection) as session:
        await session.initialize()
        tools = _serialize_tools(_wrap_take_photo(await load_mcp_tools(session)))

        agent = create_agent(llm, tools)
        await chat_loop(agent, system_prompt)

        # agent.invoke(stt_result)


if __name__ == "__main__":
    asyncio.run(main())
