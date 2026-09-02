#!/usr/bin/env python3

"""Authenticated, read-only HTTP API for the TibiaWiki SQLite snapshot."""

from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import sqlite3
import sys
import time
from contextlib import closing
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


MAX_BODY_BYTES = 16 * 1024
MAX_QUERY_BYTES = 4 * 1024
MAX_ROWS = 20
QUERY_TIMEOUT_SECONDS = 2.0
DENIED_FUNCTIONS = {"load_extension", "readfile", "writefile", "fts3_tokenizer"}
ALLOWED_SQLITE_ACTIONS = {
    sqlite3.SQLITE_FUNCTION,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_SELECT,
}
if hasattr(sqlite3, "SQLITE_RECURSIVE"):
    ALLOWED_SQLITE_ACTIONS.add(sqlite3.SQLITE_RECURSIVE)


class QueryRejected(ValueError):
    """Raised when a query violates the read-only API contract."""


def normalize_query(query: Any) -> str:
    if not isinstance(query, str):
        raise QueryRejected("The query field must be a string.")

    query = query.strip()
    if not query:
        raise QueryRejected("The query field cannot be empty.")
    if len(query.encode("utf-8")) > MAX_QUERY_BYTES:
        raise QueryRejected(f"The query exceeds {MAX_QUERY_BYTES} bytes.")
    if "\x00" in query:
        raise QueryRejected("NUL bytes are not allowed.")

    query = query.removesuffix(";").rstrip()
    if ";" in query:
        raise QueryRejected("Only one SQL statement is allowed.")
    if not re.match(r"(?is)^select\b", query):
        raise QueryRejected("Only SELECT statements are allowed.")

    return query


def _authorizer(
    action: int,
    argument_one: str | None,
    argument_two: str | None,
    database_name: str | None,
    trigger_name: str | None,
) -> int:
    del argument_one, database_name, trigger_name
    if action not in ALLOWED_SQLITE_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and (argument_two or "").lower() in DENIED_FUNCTIONS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _json_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.hex()
    return value


def execute_read_query(database_path: Path, raw_query: Any) -> dict[str, Any]:
    query = normalize_query(raw_query)
    database_uri = f"{database_path.resolve().as_uri()}?mode=ro&immutable=1"
    deadline = time.monotonic() + QUERY_TIMEOUT_SECONDS

    with closing(sqlite3.connect(database_uri, uri=True, timeout=1.0)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        connection.set_authorizer(_authorizer)
        connection.set_progress_handler(
            lambda: 1 if time.monotonic() > deadline else 0,
            1_000,
        )

        bounded_query = f"SELECT * FROM ({query}) AS result LIMIT {MAX_ROWS + 1}"
        rows = connection.execute(bounded_query).fetchall()

    truncated = len(rows) > MAX_ROWS
    serialized_rows = [
        {column: _json_value(value) for column, value in dict(row).items()}
        for row in rows[:MAX_ROWS]
    ]
    return {
        "rows": serialized_rows,
        "count": len(serialized_rows),
        "truncated": truncated,
        "max_rows": MAX_ROWS,
    }


class TibiaWikiRequestHandler(BaseHTTPRequestHandler):
    server_version = "GPTibiaHTTP/1.0"

    @property
    def application(self) -> "TibiaWikiHTTPServer":
        return self.server  # type: ignore[return-value]

    def do_GET(self) -> None:
        if self.path != "/health":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return

        self._send_json(
            HTTPStatus.OK,
            {
                "status": "healthy",
                "service": "tibiawiki-http-api",
                "database": self.application.database_path.name,
            },
        )

    def do_POST(self) -> None:
        if self.path != "/v1/query":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        if not self._is_authorized():
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "Unauthorized."})
            return

        try:
            body = self._read_json_body()
            result = execute_read_query(self.application.database_path, body.get("query"))
        except QueryRejected as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body."})
            return
        except sqlite3.Error as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"Query failed: {error}"})
            return

        self._send_json(HTTPStatus.OK, result)

    def _is_authorized(self) -> bool:
        expected = f"Bearer {self.application.api_token}"
        provided = self.headers.get("Authorization", "")
        return hmac.compare_digest(provided, expected)

    def _read_json_body(self) -> dict[str, Any]:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise QueryRejected("Invalid Content-Length header.") from error

        if content_length <= 0 or content_length > MAX_BODY_BYTES:
            raise QueryRejected(f"Body size must be between 1 and {MAX_BODY_BYTES} bytes.")
        if self.headers.get_content_type() != "application/json":
            raise QueryRejected("Content-Type must be application/json.")

        body = json.loads(self.rfile.read(content_length).decode("utf-8"))
        if not isinstance(body, dict):
            raise QueryRejected("The JSON body must be an object.")
        return body

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        response = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, message_format: str, *args: Any) -> None:
        print(
            f"{self.client_address[0]} - {message_format % args}",
            file=sys.stderr,
        )


class TibiaWikiHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        database_path: Path,
        api_token: str,
    ) -> None:
        super().__init__(address, TibiaWikiRequestHandler)
        self.database_path = database_path
        self.api_token = api_token


def read_api_token(token_file: Path) -> str:
    try:
        token = token_file.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise SystemExit(f"Unable to read API token file {token_file}: {error}") from error
    if len(token) < 32:
        raise SystemExit("The API token must contain at least 32 characters.")
    return token


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database",
        type=Path,
        default=project_root / "data" / "tibiawiki.db",
    )
    parser.add_argument(
        "--token-file",
        type=Path,
        default=project_root / ".runtime" / "tibiawiki_api_token",
    )
    parser.add_argument("--host", default=os.environ.get("TIBIAWIKI_API_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("TIBIAWIKI_API_PORT", "8080")),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.database.is_file():
        print(f"Database not found: {args.database}", file=sys.stderr)
        return 1

    server = TibiaWikiHTTPServer(
        (args.host, args.port),
        args.database.resolve(),
        read_api_token(args.token_file),
    )
    print(f"TibiaWiki HTTP API: http://{args.host}:{args.port}/v1/query")
    print(f"Health check:       http://{args.host}:{args.port}/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
