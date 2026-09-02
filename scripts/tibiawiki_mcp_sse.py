#!/usr/bin/env python3
"""Experimental SSE prototype retained for reference.

The supported launcher is start_tibiawiki_mcp.sh, which uses the pinned db-mcp
dependency. This prototype is not part of the production path.
"""

import sys
import os
import sqlite3
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.sse import SseServerTransport
import mcp.types as types

DATABASE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "tibiawiki.db")
)

server = Server("tibiawiki-sqlite")
sse = SseServerTransport("/messages")

def get_db():
    conn = sqlite3.connect(f"file:{DATABASE_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="read_query",
            description="Execute a read-only SELECT query on the TibiaWiki SQLite database. Always use LIMIT <= 20.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The SELECT SQL query to run."}
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="list_tables",
            description="List all available tables in the TibiaWiki database (e.g. creature, item, npc, quest, spell, creature_drop, imbuement).",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="describe_table",
            description="Get the column names and types for a specific table in the TibiaWiki database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Name of the table (e.g. 'creature', 'item', 'creature_drop')"}
                },
                "required": ["table_name"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    arguments = arguments or {}
    try:
        if name == "list_tables":
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                rows = [r["name"] for r in cur.fetchall()]
                return [types.TextContent(type="text", text=str(rows))]

        elif name == "describe_table":
            table_name = arguments.get("table_name", "").strip()
            if not table_name:
                return [types.TextContent(type="text", text="Missing table_name")]
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(f"PRAGMA table_info({table_name})")
                rows = [dict(r) for r in cur.fetchall()]
                return [types.TextContent(type="text", text=str(rows))]

        elif name == "read_query":
            sql = arguments.get("query", "").strip()
            if not sql.upper().startswith("SELECT"):
                return [types.TextContent(type="text", text="Error: Only SELECT statements are permitted.")]
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(sql)
                rows = [dict(r) for r in cur.fetchmany(50)]
                return [types.TextContent(type="text", text=str(rows))]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Database error: {str(e)}")]

async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        init_options = InitializationOptions(
            server_name="tibiawiki-sqlite",
            server_version="1.0.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={}
            )
        )
        await server.run(streams[0], streams[1], init_options)

async def handle_messages(request):
    await sse.handle_post_message(request.scope, request.receive, request._send)

async def handle_health(request):
    return JSONResponse({"status": "ok", "service": "tibiawiki-mcp-sse"})

app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Route("/messages", endpoint=handle_messages, methods=["POST"]),
        Route("/health", endpoint=handle_health, methods=["GET"]),
    ]
)

if __name__ == "__main__":
    host = os.environ.get("TIBIAWIKI_MCP_HOST", "127.0.0.1")
    print(f"Starting experimental TibiaWiki MCP SSE server on http://{host}:3000 ...")
    uvicorn.run(app, host=host, port=3000, log_level="info")
