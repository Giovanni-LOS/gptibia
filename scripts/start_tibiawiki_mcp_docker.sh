#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
DATABASE="$PROJECT_ROOT/data/tibiawiki.db"
COMPOSE_FILE="$PROJECT_ROOT/compose.tibiawiki-mcp.yml"

if [[ ! -f "$DATABASE" ]]; then
  echo "Database not found: $DATABASE" >&2
  echo "Run ./scripts/update_tibiawiki_db.sh first." >&2
  exit 1
fi

docker compose --file "$COMPOSE_FILE" up --detach

echo "MCP Streamable HTTP: http://127.0.0.1:3000/mcp"
echo "MCP legacy SSE:      http://127.0.0.1:3000/sse"
echo "Health check:        http://127.0.0.1:3000/health"
