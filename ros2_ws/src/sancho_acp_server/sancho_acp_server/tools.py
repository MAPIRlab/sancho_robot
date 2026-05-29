"""Tool loading, wrapping, logging, and permission gating for the Sancho ACP server.

This module intercepts MCP tool executions to emit ACP streaming events to the client
and prompts for permissions before calling sensitive tools (e.g. navigation).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Awaitable
from uuid import uuid4

from langchain_core.tools import StructuredTool
from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger("sancho_acp_server.tools")

PERMISSION_REQUIRED_TOOLS: set[str] = {
    "navigate_to_pose",
}

ToolStartCallback = Callable[[str, str, str], Awaitable[None]]
ToolEndCallback = Callable[[str, str, str], Awaitable[None]]
PermissionCallback = Callable[[str, dict[str, Any]], Awaitable[bool]]


class ToolLogger(BaseCallbackHandler):
    """Prints tool invocation traces to the server console."""

    def on_tool_start(
        self, serialized: dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        name = serialized.get("name", "unknown")
        logger.info("[tool:start] %s <- %s", name, input_str)

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        name = kwargs.get("name", "unknown")
        logger.info("[tool:end] %s -> %s", name, summarize_tool_output(output))


def summarize_tool_output(output: Any) -> str:
    """Create a short, human-readable summary of a tool's return value.

    Handles raw strings, dicts, lists, and LangChain ``ToolMessage``
    objects (which have a ``.content`` attribute).
    """
    if hasattr(output, "content"):
        output = output.content

    if isinstance(output, str):
        return output if len(output) <= 500 else f"{output[:500]}..."

    if isinstance(output, list):
        texts: list[str] = []
        for part in output:
            if isinstance(part, dict):
                if part.get("type") == "image_url":
                    return "<image payload>"
                if part.get("type") == "text":
                    texts.append(str(part.get("text", "")))
        if texts:
            joined = "\n".join(texts)
            return joined if len(joined) <= 500 else f"{joined[:500]}..."
        return str(output)[:500]

    if isinstance(output, dict):
        if output.get("type") == "image":
            data_len = len(str(output.get("data", "")))
            return f"<image payload bytes={data_len}>"
        if "error" in output:
            return f"error: {output['error']}"

    text = str(output)
    return text if len(text) <= 500 else f"{text[:500]}..."


def _mcp_image_payload_to_content(payload: Any) -> Any:
    """Convert MCP image payloads into LangChain multimodal content blocks."""
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

    if isinstance(payload, str):
        try:
            data = json.loads(payload)
            if isinstance(data, dict) and data.get("type") == "image":
                return _create_multimodal_content(data)
        except json.JSONDecodeError:
            pass

    if isinstance(payload, dict) and payload.get("type") == "image":
        return _create_multimodal_content(payload)

    return payload


def _create_multimodal_content(data: dict[str, Any]) -> list[dict[str, Any]]:
    b64_data = data.get("data")
    if not b64_data:
        return [{"type": "text", "text": "error: Empty image payload"}]
    mime = data.get("mime_type") or data.get("mimeType") or "image/jpeg"
    data_url = f"data:{mime};base64,{b64_data}"
    return [
        {"type": "text", "text": "Captured image from robot camera."},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]


async def _call_tool(tool: Any, args: dict[str, Any]) -> Any:
    """Invoke a LangChain tool, handling both sync and async variants."""
    if hasattr(tool, "ainvoke"):
        return await tool.ainvoke(args)
    return await asyncio.to_thread(tool.invoke, args)


def wrap_take_photo(tools: list[Any]) -> list[Any]:
    """Wrap the ``take_photo`` tool so its raw base64 image is converted
    into a multimodal content block that the LLM can interpret directly."""
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
    return [t for t in tools if t.name != "take_photo"] + [wrapped]


@dataclass
class _ToolWrapper:
    """Encapsulates tool wrapping logic with explicit dependencies."""

    tool: Any
    needs_permission: bool
    on_tool_start: ToolStartCallback | None
    on_tool_end: ToolEndCallback | None
    permission_callback: PermissionCallback | None

    async def invoke(self, **kwargs: Any) -> Any:
        """Execute the tool with streaming notifications and permission gating."""
        tool_call_id = uuid4().hex[:12]
        input_summary = json.dumps(kwargs, ensure_ascii=False, default=str)

        await self._notify_start(tool_call_id, input_summary)

        if self.needs_permission:
            approved = await self._check_permission(kwargs)
            if not approved:
                return self._denied_message(tool_call_id)

        output = await self._execute(kwargs)
        await self._notify_end(tool_call_id, output)
        return output

    def _make_sync_wrapper(self) -> Callable[..., Any]:
        async def _async_invoke(**kwargs: Any) -> Any:
            return await self.invoke(**kwargs)

        def _sync_invoke(**kwargs: Any) -> Any:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                return asyncio.run_coroutine_threadsafe(
                    _async_invoke(**kwargs), loop
                ).result()
            return asyncio.run(_async_invoke(**kwargs))

        return _sync_invoke

    async def _notify_start(self, tool_call_id: str, input_summary: str) -> None:
        if self.on_tool_start:
            await self.on_tool_start(tool_call_id, self.tool.name, input_summary)

    async def _check_permission(self, args: dict[str, Any]) -> bool:
        if self.permission_callback is None:
            return True
        return await self.permission_callback(self.tool.name, args)

    def _denied_message(self, tool_call_id: str) -> str:
        msg = f"⛔ User denied permission for '{self.tool.name}'. The action was NOT executed."
        if self.on_tool_end:
            asyncio.create_task(
                self.on_tool_end(tool_call_id, self.tool.name, msg)
            )
        return msg

    async def _execute(self, args: dict[str, Any]) -> Any:
        try:
            return await _call_tool(self.tool, args)
        except Exception as exc:
            error_msg = f"Tool error: {exc}"
            if self.on_tool_end:
                await self.on_tool_end(tool_call_id := uuid4().hex[:12], self.tool.name, error_msg)
            raise

    async def _notify_end(self, tool_call_id: str, output: Any) -> None:
        if self.on_tool_end:
            summary = summarize_tool_output(output)
            await self.on_tool_end(tool_call_id, self.tool.name, summary)


def wrap_all_tools(
    tools: list[Any],
    *,
    on_tool_start: ToolStartCallback | None = None,
    on_tool_end: ToolEndCallback | None = None,
    permission_callback: PermissionCallback | None = None,
) -> list[Any]:
    """Wrap every tool to emit ACP streaming notifications and, for
    sensitive tools, request user permission before execution.
    """
    result: list[Any] = []
    for tool in tools:
        needs_permission = (
            tool.name in PERMISSION_REQUIRED_TOOLS
            and permission_callback is not None
        )

        wrapper = _ToolWrapper(
            tool=tool,
            needs_permission=needs_permission,
            on_tool_start=on_tool_start,
            on_tool_end=on_tool_end,
            permission_callback=permission_callback,
        )

        wrapped = StructuredTool.from_function(
            name=tool.name,
            description=tool.description or tool.name,
            func=wrapper._make_sync_wrapper(),
            coroutine=wrapper.invoke,
            args_schema=getattr(tool, "args_schema", None),
        )
        result.append(wrapped)

    return result