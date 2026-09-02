#!/usr/bin/env bash

set -euo pipefail

PORT="${TIBIAWIKI_API_PORT:-8080}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared was not found in PATH." >&2
  exit 1
fi

if ! curl --fail --silent "http://127.0.0.1:$PORT/health" >/dev/null; then
  echo "The TibiaWiki HTTP API is not healthy on port $PORT." >&2
  echo "Start it with ./scripts/start_tibiawiki_http_api.sh" >&2
  exit 1
fi

echo "Starting an ephemeral HTTPS tunnel to http://127.0.0.1:$PORT"
echo "Use the generated https://*.trycloudflare.com URL with /v1/query."
exec cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT"
