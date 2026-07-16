"""ContextOS MCP server — exposes the user's own context to Claude Code / Cursor / any
MCP client, so their context follows them across AI tools.

Every tool returns REAL ContextOS + Supermemory data by calling the local ContextOS backend
(http://localhost:8765). No secrets are exposed — the backend redacts before serving.

Run (stdio):
    python contextos_mcp.py
Register in Claude Code:  see mcp-server/README.md
"""
from __future__ import annotations

import json
import os

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

BASE = os.environ.get("CONTEXTOS_API", "http://127.0.0.1:8765")
server = Server("contextos")


async def _get(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(base_url=BASE, timeout=20.0) as c:
        r = await c.get(path, params=params)
        r.raise_for_status()
        return r.json()


async def _post(path: str, body: dict) -> dict:
    async with httpx.AsyncClient(base_url=BASE, timeout=20.0) as c:
        r = await c.post(path, json=body)
        r.raise_for_status()
        return r.json()


TOOLS = [
    Tool(name="get_context_passport",
         description="The user's portable Context Passport: goal, project, task, active session, "
                     "recent work, decisions, blockers, related memory, and suggested next action. "
                     "Use this to instantly understand what the user is working on.",
         inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_current_context",
         description="What the user is doing right now: application, project, repository, branch, file.",
         inputSchema={"type": "object", "properties": {}}),
    Tool(name="search_user_memory",
         description="Semantically search the user's own local memory (Supermemory) across all apps.",
         inputSchema={"type": "object",
                      "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
                      "required": ["query"]}),
    Tool(name="get_active_session",
         description="The user's current Context Session (grouped related work).",
         inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_project_context",
         description="Memories, files, decisions and blockers for a specific project.",
         inputSchema={"type": "object", "properties": {"project": {"type": "string"}},
                      "required": ["project"]}),
    Tool(name="get_recent_activity",
         description="The user's recent meaningful activity, newest first.",
         inputSchema={"type": "object", "properties": {"limit": {"type": "integer"}}}),
    Tool(name="get_recent_decisions",
         description="Technical decisions the user recently made (derived from real memory).",
         inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_current_blockers",
         description="Errors/blockers the user is currently facing (derived from real memory).",
         inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_related_memories",
         description="Memories related to a topic or the current context.",
         inputSchema={"type": "object", "properties": {"query": {"type": "string"}},
                      "required": ["query"]}),
    Tool(name="get_recent_files",
         description="Files the user recently worked on.",
         inputSchema={"type": "object", "properties": {}}),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "get_context_passport":
            data = await _get("/api/context/passport")
        elif name == "get_current_context":
            data = await _get("/api/context/current")
        elif name == "search_user_memory":
            data = await _post("/api/search", {"q": arguments["query"], "limit": arguments.get("limit", 8)})
        elif name == "get_active_session":
            sessions = await _get("/api/sessions")
            data = (sessions.get("sessions") or [None])[0]
        elif name == "get_project_context":
            data = await _get(f"/api/context/project/{arguments['project']}")
        elif name == "get_recent_activity":
            data = await _get("/api/activity/recent", {"limit": arguments.get("limit", 20)})
        elif name == "get_recent_decisions":
            data = await _get("/api/context/decisions")
        elif name == "get_current_blockers":
            data = await _get("/api/context/blockers")
        elif name == "get_related_memories":
            data = await _post("/api/related", {"query": arguments["query"]})
        elif name == "get_recent_files":
            data = await _get("/api/context/passport")
            data = {"recent_files": data.get("recent_files", [])}
        else:
            data = {"error": f"unknown tool {name}"}
        # diagnostics: note the grounding source
        if isinstance(data, dict):
            data.setdefault("_source", "ContextOS + Supermemory Local (real user data)")
        return [TextContent(type="text", text=json.dumps(data, indent=2, default=str))]
    except Exception as exc:  # noqa: BLE001
        return [TextContent(type="text", text=json.dumps(
            {"error": str(exc), "hint": "Is the ContextOS backend running at " + BASE + "?"}))]


async def main() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
