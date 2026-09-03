#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data"
FINAL_DB="$DATA_DIR/tibiawiki.db"
FINAL_KNOWLEDGE="$DATA_DIR/rag_knowledge.json"

if ! command -v tibiawikisql >/dev/null 2>&1; then
  echo "tibiawikisql was not found in PATH." >&2
  echo "Install it with: pipx install tibiawikisql==9.0.0" >&2
  exit 1
fi

mkdir -p "$DATA_DIR"
TEMP_DB="$(mktemp --tmpdir="$DATA_DIR" .tibiawiki.XXXXXX.db)"
TEMP_KNOWLEDGE="$(mktemp --tmpdir="$DATA_DIR" .rag_knowledge.XXXXXX.json)"

cleanup() {
  rm -f -- "$TEMP_DB"
  rm -f -- "$TEMP_KNOWLEDGE"
}
trap cleanup EXIT

echo "Generating TibiaWiki database..."
(
  cd "$DATA_DIR"
  tibiawikisql generate \
    --skip-images \
    --skip-deprecated \
    --log-parsing-errors \
    --db-name "$TEMP_DB"
)

python3 "$SCRIPT_DIR/create_tibiawiki_views.py" "$TEMP_DB"
python3 "$SCRIPT_DIR/validate_tibiawiki_db.py" "$TEMP_DB"
python3 "$SCRIPT_DIR/export_rag_knowledge.py" "$TEMP_DB" --output "$TEMP_KNOWLEDGE"
mv -f -- "$TEMP_DB" "$FINAL_DB"
chmod 0644 "$FINAL_DB"
mv -f -- "$TEMP_KNOWLEDGE" "$FINAL_KNOWLEDGE"
chmod 0644 "$FINAL_KNOWLEDGE"
trap - EXIT

echo "Database updated: $FINAL_DB"
echo "RAG knowledge updated: $FINAL_KNOWLEDGE"
