"""Dependency-free MCP stdio server for WorkBuddy Delegate."""
from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Callable

from workbuddy_bridge import BridgeError, VERSION, delegate, plan, read_result, status, usage


PROTOCOL_VERSION = "2025-06-18"


TOOLS: list[dict[str, Any]] = [
    {
        "name": "workbuddy_status",
        "description": "Check the local WorkBuddy bridge, configured limits, and installation without sending a model request.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "workbuddy_plan",
        "description": "Classify eligibility for bounded delegation without reading files or sending a model request.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "instruction": {"type": "string", "minLength": 1, "maxLength": 6000},
                "kind": {"type": "string"},
                "risk": {"type": "string"},
            },
            "required": ["instruction", "kind", "risk"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "delegate_to_workbuddy",
        "description": (
            "Send one bounded low-risk text task to the user's installed WorkBuddy. Use explicit relative files "
            "or short provided text. Supported kinds: summarize, extract, classify, translate, rewrite, code_draft. "
            "Only risk=low is routed. The main agent must verify the returned result."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "instruction": {"type": "string", "minLength": 1, "maxLength": 6000},
                "workspace": {"type": "string", "minLength": 1},
                "kind": {"type": "string", "enum": ["summarize", "extract", "classify", "translate", "rewrite", "code_draft"]},
                "risk": {"type": "string", "enum": ["low"]},
                "files": {"type": "array", "items": {"type": "string"}, "maxItems": 24, "default": []},
                "text": {"type": "string", "default": ""},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["instruction", "workspace", "kind", "risk"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
    {
        "name": "workbuddy_read_result",
        "description": "Read a plugin-created result artifact when its short preview was truncated.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "artifact": {"type": "string", "minLength": 1},
                "max_chars": {"type": "integer", "minimum": 100, "maximum": 12000, "default": 12000},
            },
            "required": ["artifact"],
            "additionalProperties": False,
        },
    },
    {
        "name": "workbuddy_usage",
        "description": "Show local invocation counts. This does not call WorkBuddy or estimate money.",
        "inputSchema": {
            "type": "object",
            "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 90, "default": 7}},
            "additionalProperties": False,
        },
    },
]


def _dispatch(name: str, arguments: dict[str, Any]) -> Any:
    handlers: dict[str, Callable[..., Any]] = {
        "workbuddy_status": status,
        "workbuddy_plan": plan,
        "delegate_to_workbuddy": delegate,
        "workbuddy_read_result": read_result,
        "workbuddy_usage": usage,
    }
    if name not in handlers:
        raise BridgeError(f"Unknown tool: {name}")
    return handlers[name](**arguments)


def _result(request_id: Any, value: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": value}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    request_id = message.get("id")
    method = message.get("method")
    if not isinstance(method, str):
        return _error(request_id, -32600, "Invalid Request") if "id" in message else None
    if method == "initialize":
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        requested = params.get("protocolVersion")
        protocol = requested if isinstance(requested, str) and requested else PROTOCOL_VERSION
        return _result(
            request_id,
            {
                "protocolVersion": protocol,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "workbuddy-delegate", "version": VERSION},
                "instructions": "Delegate only bounded low-risk work. Codex must review returned results.",
            },
        )
    if method in {"notifications/initialized", "initialized", "notifications/cancelled"}:
        return None
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params")
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            return _error(request_id, -32602, "Invalid tool call parameters")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            return _error(request_id, -32602, "Tool arguments must be an object")
        try:
            value = _dispatch(params["name"], arguments)
            text = json.dumps(value, ensure_ascii=False)
            return _result(
                request_id,
                {
                    "content": [{"type": "text", "text": text}],
                    "structuredContent": value if isinstance(value, dict) else {"value": value},
                    "isError": False,
                },
            )
        except (BridgeError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            value = {"status": "blocked", "error": str(exc), "fallback": "main_agent"}
            return _result(
                request_id,
                {
                    "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}],
                    "structuredContent": value,
                    "isError": True,
                },
            )
    return _error(request_id, -32601, "Method not found") if "id" in message else None


def serve() -> int:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            incoming = json.loads(line)
            outgoing = handle(incoming) if isinstance(incoming, dict) else _error(None, -32600, "Invalid Request")
        except json.JSONDecodeError:
            outgoing = _error(None, -32700, "Parse error")
        except Exception as exc:  # Keep the transport alive without leaking local traces to the client.
            print(traceback.format_exc(), file=sys.stderr, flush=True)
            outgoing = _error(None, -32603, f"Internal error: {type(exc).__name__}")
        if outgoing is not None:
            print(json.dumps(outgoing, ensure_ascii=False, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(serve())
