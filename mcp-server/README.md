# ContextOS MCP Server

Exposes your **own** computer context — Context Passport, current activity, sessions,
decisions, blockers, and semantic memory — to Claude Code, Cursor, and any MCP client.
This is how *your context follows you*: switch AI tools, keep your context.

Every tool returns **real** ContextOS + Supermemory data by calling the local ContextOS
backend (`http://localhost:8765`). The backend applies privacy redaction, so no secrets are
exposed.

## Tools
`get_context_passport`, `get_current_context`, `search_user_memory`, `get_active_session`,
`get_project_context`, `get_recent_activity`, `get_recent_decisions`, `get_current_blockers`,
`get_related_memories`, `get_recent_files`.

## Prerequisites
- ContextOS backend running at `http://localhost:8765`.
- The MCP SDK (already installed in the backend venv): `pip install "mcp>=1.2"`.

## Register in Claude Code
```bash
claude mcp add contextos -- <abs-path>/backend/.venv/Scripts/python.exe <abs-path>/mcp-server/contextos_mcp.py
```
Or add to your MCP config (`claude_desktop_config.json` / Cursor `mcp.json`):
```json
{
  "mcpServers": {
    "contextos": {
      "command": "D:/ContextOS/backend/.venv/Scripts/python.exe",
      "args": ["D:/ContextOS/mcp-server/contextos_mcp.py"],
      "env": { "CONTEXTOS_API": "http://127.0.0.1:8765" }
    }
  }
}
```

## Try it
In Claude Code, ask: *"Use ContextOS to load my context passport and continue where I left
off."* Claude will call `get_context_passport` and pick up your real goal, project, recent
work, decisions, and next action — no re-explaining.

## Manual action required
Registering the server in an AI tool is a one-time manual step (Claude Code `claude mcp add`
or editing the client's MCP config). ContextOS cannot register itself into your AI client.
