#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
RUNTIME_DIR="$PROJECT_ROOT/.runtime"
TOKEN_FILE="$RUNTIME_DIR/tibiawiki_api_token"

mkdir -p "$RUNTIME_DIR"
chmod 0700 "$RUNTIME_DIR"

if [[ ! -s "$TOKEN_FILE" ]]; then
  umask 077
  openssl rand -hex 32 > "$TOKEN_FILE"
fi
chmod 0600 "$TOKEN_FILE"

echo "API token file: $TOKEN_FILE"
exec python3 "$SCRIPT_DIR/tibiawiki_http_api.py" --token-file "$TOKEN_FILE" "$@"
