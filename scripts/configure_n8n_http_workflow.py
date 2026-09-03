#!/usr/bin/env python3

"""Create an ignored n8n workflow with the HTTP API URL and token injected."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse


API_URL_PLACEHOLDER = "__TIBIAWIKI_API_URL__"
API_TOKEN_PLACEHOLDER = "__TIBIAWIKI_API_TOKEN__"
TOOL_NODE_NAME = "TibiaWiki - HTTP SQL"
KNOWLEDGE_NODE_NAME = "Baixar Tibia Knowledge"


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

    workflow = json.loads(args.template.read_text(encoding="utf-8"))
    tool_node = next(
        (node for node in workflow["nodes"] if node.get("name") == TOOL_NODE_NAME),
        None,
    )
    if tool_node is None:
        raise SystemExit(f"Node not found in template: {TOOL_NODE_NAME}")
    knowledge_node = next(
        (node for node in workflow["nodes"] if node.get("name") == KNOWLEDGE_NODE_NAME),
        None,
    )
    if knowledge_node is None:
        raise SystemExit(f"Node not found in template: {KNOWLEDGE_NODE_NAME}")

    code = tool_node["parameters"]["jsCode"]
    if API_URL_PLACEHOLDER not in code or API_TOKEN_PLACEHOLDER not in code:
        raise SystemExit("The workflow template does not contain the expected placeholders.")

    base_url = args.api_url.rstrip("/")
    if base_url.endswith("/v1/query"):
        base_url = base_url.removesuffix("/v1/query")
    endpoint = f"{base_url}/v1/query"
    tool_node["parameters"]["jsCode"] = code.replace(
        API_URL_PLACEHOLDER,
        endpoint,
    ).replace(API_TOKEN_PLACEHOLDER, token)

    knowledge_url = knowledge_node["parameters"].get("url", "")
    header_parameters = knowledge_node["parameters"].get("headerParameters", {}).get(
        "parameters", []
    )
    authorization_header = next(
        (header for header in header_parameters if header.get("name") == "Authorization"),
        None,
    )
    if "__TIBIAWIKI_KNOWLEDGE_URL__" not in knowledge_url or authorization_header is None:
        raise SystemExit("The knowledge node does not contain the expected placeholders.")
    knowledge_node["parameters"]["url"] = knowledge_url.replace(
        "__TIBIAWIKI_KNOWLEDGE_URL__",
        f"{base_url}/v1/knowledge",
    )
    authorization_header["value"] = authorization_header["value"].replace(
        API_TOKEN_PLACEHOLDER,
        token,
    )

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
