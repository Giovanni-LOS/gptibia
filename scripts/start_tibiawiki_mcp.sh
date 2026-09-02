#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
DATABASE="$PROJECT_ROOT/data/tibiawiki.db"
MCP_SERVER="$PROJECT_ROOT/mcp/tibiawiki_sse_server.mjs"
RUNTIME_DIR="$PROJECT_ROOT/.runtime"
TOKEN_FILE="$RUNTIME_DIR/tibiawiki_mcp_token"

if [[ ! -f "$DATABASE" ]]; then
  echo "Database not found: $DATABASE" >&2
  echo "Run ./scripts/update_tibiawiki_db.sh first." >&2
  exit 1
fi

NODE_MAJOR="$(node --version | sed -E 's/^v([0-9]+).*/\1/')"
if (( NODE_MAJOR < 26 )); then
  echo "Node.js 26 or newer is required. Current version: $(node --version)" >&2
  exit 1
fi

if [[ ! -d "$PROJECT_ROOT/mcp/node_modules/@modelcontextprotocol/sdk" ]]; then
  echo "MCP dependencies are not installed." >&2
  echo "Run: npm install --prefix $PROJECT_ROOT/mcp" >&2
  exit 1
fi

mkdir -p "$RUNTIME_DIR"
chmod 0700 "$RUNTIME_DIR"
if [[ ! -s "$TOKEN_FILE" ]]; then
  umask 077
  openssl rand -hex 32 > "$TOKEN_FILE"
fi
chmod 0600 "$TOKEN_FILE"

export TIBIAWIKI_MCP_TOKEN_FILE="$TOKEN_FILE"
export TIBIAWIKI_DATABASE="$DATABASE"

echo "MCP legacy SSE: http://127.0.0.1:3000/sse"
echo "Health check:   http://127.0.0.1:3000/health"
echo "Bearer token:   $TOKEN_FILE"

exec node "$MCP_SERVER"
