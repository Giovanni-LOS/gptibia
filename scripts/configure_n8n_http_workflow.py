#!/usr/bin/env python3

"""Create an ignored n8n workflow with HTTP API URLs and token injected."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", required=True)
    parser.add_argument(
        "--token-file",
        type=Path,
        default=project_root / ".runtime" / "tibiawiki_api_token",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=project_root / "gptibia_telegram_workflow.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "gptibia_telegram_workflow.local.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    parsed_url = urlparse(args.api_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise SystemExit("--api-url must be a public HTTPS URL.")

    token = args.token_file.read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise SystemExit("The API token must contain at least 32 characters.")

    base_url = args.api_url.rstrip("/")
    for suffix in ("/v1/query", "/v1/quest", "/v1/creature", "/v1/item", "/v1/knowledge"):
        if base_url.endswith(suffix):
            base_url = base_url.removesuffix(suffix)
            break

    raw_template = args.template.read_text(encoding="utf-8")
    replaced = (
        raw_template.replace("__TIBIAWIKI_QUEST_URL__", f"{base_url}/v1/quest")
        .replace("__TIBIAWIKI_CREATURE_URL__", f"{base_url}/v1/creature")
        .replace("__TIBIAWIKI_ITEM_URL__", f"{base_url}/v1/item")
        .replace("__TIBIAWIKI_API_URL__", f"{base_url}/v1/query")
        .replace("__TIBIAWIKI_KNOWLEDGE_URL__", f"{base_url}/v1/knowledge")
        .replace("__TIBIAWIKI_API_TOKEN__", token)
    )

    workflow = json.loads(replaced)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = args.output.with_suffix(f"{args.output.suffix}.tmp")
    temporary_output.write_text(
        json.dumps(workflow, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary_output, 0o600)
    os.replace(temporary_output, args.output)
    print(f"Configured workflow written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
