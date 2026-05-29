"""Tool loading, wrapping, logging, and permission gating for the Sancho ACP server.

This module intercepts MCP tool executions to emit ACP streaming events to the client
and prompts for permissions before calling sensitive tools (e.g. navigation).
"""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import uuid4
from typing import Any, Callable, Awaitable

from langchain_core.tools import StructuredTool
from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger("sancho_acp_server.tools")

# Tools that require explicit human authorization via ACP before execution.
PERMISSION_REQUIRED_TOOLS: set[str] = {
    "navigate_to_pose",
}


class ToolLogger(BaseCallbackHandler):
    """Prints tool invocation traces to the server console."""

    def on_tool_start(
        self, serialized: dict, input_str: str, **kwargs: Any
    ) -> None:
        name = serialized.get("name", "tool")
        logger.info("[tool:start] %s <- %s", name, input_str)

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        name = kwargs.get("name", "tool")
        logger.info("[tool:end] %s -> %s", name, _summarize_tool_output(output))


def _summarize_tool_output(output: Any) -> str:
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


async def _call_tool(tool: Any, args: dict) -> Any:
    """Invoke a LangChain tool, handling both sync and async variants."""
    if hasattr(tool, "ainvoke"):
        return await tool.ainvoke(args)
    return await asyncio.to_thread(tool.invoke, args)


def _wrap_take_photo(tools: list[Any]) -> list[Any]:
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
        description=(
            raw_tool.description
            or "Capture a camera frame as an image payload."
        ),
        coroutine=_take_photo,
    )
    return [t for t in tools if t.name != "take_photo"] + [wrapped]


# Type aliases for async callbacks from the tool wrappers.
ToolStartCallback = Callable[[str, str, str], Awaitable[None]]
ToolEndCallback = Callable[[str, str, str], Awaitable[None]]
PermissionCallback = Callable[[str, dict[str, Any]], Awaitable[bool]]


def _wrap_all_tools(
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
        original = tool
        needs_permission = (
            original.name in PERMISSION_REQUIRED_TOOLS
            and permission_callback is not None
        )

        async def _instrumented_invoke(
            _orig=original,
            _perm=needs_permission,
            **kwargs: Any,
        ) -> Any:
            logger.info("Inside _instrumented_invoke for tool: %s, args: %s", _orig.name, kwargs)
            tool_call_id = uuid4().hex[:12]
            input_summary = json.dumps(kwargs, ensure_ascii=False, default=str)

            # ── Notify ACP: tool is starting ──
            if on_tool_start:
                await on_tool_start(tool_call_id, _orig.name, input_summary)

            # ── Permission gate (only for sensitive tools) ──
            if _perm and permission_callback is not None:
                approved = await permission_callback(_orig.name, kwargs)
                if not approved:
                    denied_msg = (
                        f"⛔ User denied permission for '{_orig.name}'. "
                        "The action was NOT executed."
                    )
                    if on_tool_end:
                        await on_tool_end(tool_call_id, _orig.name, denied_msg)
                    return denied_msg

            # ── Execute the real tool ──
            try:
                output = await _call_tool(_orig, kwargs)
            except Exception as exc:
                error_msg = f"Tool error: {exc}"
                if on_tool_end:
                    await on_tool_end(tool_call_id, _orig.name, error_msg)
                raise

            # ── Notify ACP: tool finished ──
            if on_tool_end:
                summary = _summarize_tool_output(output)
                await on_tool_end(tool_call_id, _orig.name, summary)

            return output

        def _sync_wrapper(
            _orig=original,
            _perm=needs_permission,
            **kwargs: Any,
        ) -> Any:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                return asyncio.run_coroutine_threadsafe(
                    _instrumented_invoke(_orig=_orig, _perm=_perm, **kwargs),
                    loop
                ).result()
            else:
                return asyncio.run(_instrumented_invoke(_orig=_orig, _perm=_perm, **kwargs))

        wrapped = StructuredTool.from_function(
            name=original.name,
            description=original.description or original.name,
            func=_sync_wrapper,
            coroutine=_instrumented_invoke,
            args_schema=getattr(original, "args_schema", None),
        )
        result.append(wrapped)

    return result
