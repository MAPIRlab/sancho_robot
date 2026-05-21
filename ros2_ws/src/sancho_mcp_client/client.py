from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

from langchain_mcp_adapters.sessions import create_session
from langchain_mcp_adapters.tools import load_mcp_tools

DEFAULT_PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "sancho_mcp_server" / "SYSTEM_PROMPT.md"
)


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
    if isinstance(payload, dict) and payload.get("type") == "image":
        data = payload.get("data")
        if not data:
            return {"error": "Empty image payload from take_photo"}
        mime = payload.get("mime_type", "image/jpeg")
        data_url = f"data:{mime};base64,{data}"
        return [
            {"type": "text", "text": "Captured image from robot camera."},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]
    return payload


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
        description=raw_tool.description or "Capture a camera frame as an image payload.",
        coroutine=_take_photo,
    )

    return [tool for tool in tools if tool.name != "take_photo"] + [wrapped]


def _build_llm() -> ChatGoogleGenerativeAI:
    load_dotenv()
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is required for Gemini.")

    model = os.environ.get("SANCHO_MCP_LLM_MODEL", "gemini-3.1-flash-lite")
    temperature = float(os.environ.get("SANCHO_MCP_LLM_TEMPERATURE", "0.2"))

    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        temperature=temperature,
    )


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
        messages = result.get("messages", messages)
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
        tools = _wrap_take_photo(await load_mcp_tools(session))

        agent = create_agent(llm, tools)
        await chat_loop(agent, system_prompt)


if __name__ == "__main__":
    asyncio.run(main())
