#!/usr/bin/env python3

"""Authenticated, read-only HTTP API for the TibiaWiki SQLite snapshot.

Includes raw SQL execution, RAG knowledge serving, and dedicated domain
tools for quests, creatures, and items with intelligent name resolution,
fuzzy typo matching, and correlated audit logging.
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import hmac
import json
import os
import re
import sqlite3
import sys
import time
import uuid
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


class KnowledgeUnavailable(RuntimeError):
    """Raised when the generated RAG corpus is missing or invalid."""


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


def _connect_ro(database_path: Path) -> sqlite3.Connection:
    database_uri = f"{database_path.resolve().as_uri()}?mode=ro&immutable=1"
    connection = sqlite3.connect(database_uri, uri=True, timeout=1.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def get_snapshot_timestamp(connection: sqlite3.Connection) -> str | None:
    """Read generation timestamp from database_info."""
    try:
        row = connection.execute(
            "SELECT value FROM database_info WHERE key = 'generate_time'"
        ).fetchone()
        if row and row["value"]:
            return str(row["value"])
    except sqlite3.Error:
        pass
    return None


def execute_read_query(database_path: Path, raw_query: Any) -> dict[str, Any]:
    query = normalize_query(raw_query)
    deadline = time.monotonic() + QUERY_TIMEOUT_SECONDS

    with closing(_connect_ro(database_path)) as connection:
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


def _clean_for_fuzzy(text: str, table: str) -> str:
    s = text.lower().strip()
    if table == "quest":
        if s.startswith("the "):
            s = s[4:]
        if s.endswith(" quest"):
            s = s[:-6]
    return s


def resolve_entity(
    connection: sqlite3.Connection,
    table: str,
    raw_name: Any,
) -> tuple[str, dict[str, Any] | None, list[str]]:
    """Resolve an entity in a given table by exact, canonical, partial, or fuzzy match.

    Returns:
        (match_type, matched_row_dict_or_None, list_of_candidate_titles)
        match_type can be: 'exact', 'partial', 'fuzzy', 'ambiguous', or 'not_found'.
    """
    if not isinstance(raw_name, str) or not raw_name.strip():
        return "not_found", None, []

    name = raw_name.strip()

    # 1. Exact title match
    cur = connection.execute(
        f"SELECT * FROM {table} WHERE title = ? COLLATE NOCASE",
        (name,),
    )
    rows = cur.fetchall()
    if len(rows) == 1:
        return "exact", dict(rows[0]), []

    # 2. Exact name match
    cur = connection.execute(
        f"SELECT * FROM {table} WHERE name = ? COLLATE NOCASE",
        (name,),
    )
    rows = cur.fetchall()
    if len(rows) == 1:
        return "exact", dict(rows[0]), []

    # 3. Canonical prefixes/suffixes for quests
    if table == "quest":
        cur = connection.execute(
            "SELECT * FROM quest WHERE title = ? COLLATE NOCASE",
            (f"The {name} Quest",),
        )
        r = cur.fetchall()
        if len(r) == 1:
            return "partial", dict(r[0]), []

        cur = connection.execute(
            "SELECT * FROM quest WHERE title = ? COLLATE NOCASE",
            (f"{name} Quest",),
        )
        r = cur.fetchall()
        if len(r) == 1:
            return "partial", dict(r[0]), []

    # 4. Partial LIKE match
    cur = connection.execute(
        f"SELECT * FROM {table} WHERE title LIKE ? ORDER BY LENGTH(title) ASC LIMIT 10",
        (f"%{name}%",),
    )
    like_rows = cur.fetchall()
    if len(like_rows) == 1:
        return "partial", dict(like_rows[0]), []
    elif len(like_rows) > 1:
        for r in like_rows:
            if r["title"].lower() == name.lower():
                return "exact", dict(r), []
        return "ambiguous", None, [r["title"] for r in like_rows[:6]]

    # 5. Fuzzy match for typos (SequenceMatcher)
    all_rows = connection.execute(f"SELECT * FROM {table}").fetchall()
    q_clean = _clean_for_fuzzy(name, table)
    scored: list[tuple[float, sqlite3.Row]] = []
    for r in all_rows:
        t_clean = _clean_for_fuzzy(r["title"], table)
        n_clean = _clean_for_fuzzy(r["name"] or "", table)
        ratio = max(
            difflib.SequenceMatcher(None, q_clean, t_clean).ratio(),
            difflib.SequenceMatcher(None, q_clean, n_clean).ratio(),
        )
        if ratio >= 0.65:
            scored.append((ratio, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return "not_found", None, []

    if len(scored) == 1 or (scored[0][0] - scored[1][0] >= 0.08):
        return "fuzzy", dict(scored[0][1]), [s[1]["title"] for s in scored[:5]]

    return "ambiguous", None, [s[1]["title"] for s in scored[:6]]


def get_quest_overview(database_path: Path, raw_name: Any) -> dict[str, Any]:
    """Fetch structured quest overview with dangers and rewards."""
    with closing(_connect_ro(database_path)) as connection:
        match_type, quest, candidates = resolve_entity(connection, "quest", raw_name)
        snapshot_time = get_snapshot_timestamp(connection)

        if quest is None:
            return {
                "entity": raw_name if isinstance(raw_name, str) else "",
                "match_type": match_type,
                "candidates": candidates,
                "data": None,
                "snapshot_timestamp": snapshot_time,
                "article_timestamp": None,
            }

        quest_id = quest["article_id"]
        dangers = connection.execute(
            """
            SELECT cr.title AS name, cr.hitpoints, cr.experience, cr.creature_class
            FROM quest_danger qd
            JOIN creature cr ON cr.article_id = qd.creature_id
            WHERE qd.quest_id = ?
            ORDER BY cr.hitpoints DESC, cr.title ASC
            """,
            (quest_id,),
        ).fetchall()

        rewards = connection.execute(
            """
            SELECT it.title AS name
            FROM quest_reward qr
            JOIN item it ON it.article_id = qr.item_id
            WHERE qr.quest_id = ?
            ORDER BY it.title ASC
            """,
            (quest_id,),
        ).fetchall()

        return {
            "entity": quest["title"],
            "match_type": match_type,
            "candidates": candidates,
            "data": {
                "title": quest["title"],
                "name": quest["name"],
                "location": quest["location"],
                "level_required": quest["level_required"],
                "level_recommended": quest["level_recommended"],
                "is_premium": bool(quest.get("is_premium")),
                "quest_log": quest.get("quest_log"),
                "legend": quest.get("legend"),
                "dangers": [dict(d) for d in dangers],
                "rewards": [r["name"] for r in rewards],
            },
            "snapshot_timestamp": snapshot_time,
            "article_timestamp": quest.get("timestamp"),
        }


def get_creature_profile(database_path: Path, raw_name: Any) -> dict[str, Any]:
    """Fetch structured creature profile with elemental modifiers, drops, and quests."""
    with closing(_connect_ro(database_path)) as connection:
        match_type, creature, candidates = resolve_entity(connection, "creature", raw_name)
        snapshot_time = get_snapshot_timestamp(connection)

        if creature is None:
            return {
                "entity": raw_name if isinstance(raw_name, str) else "",
                "match_type": match_type,
                "candidates": candidates,
                "data": None,
                "snapshot_timestamp": snapshot_time,
                "article_timestamp": None,
            }

        creature_id = creature["article_id"]
        drops = connection.execute(
            """
            SELECT it.title AS item, cd.chance, cd.min, cd.max
            FROM creature_drop cd
            JOIN item it ON it.article_id = cd.item_id
            WHERE cd.creature_id = ?
            ORDER BY cd.chance DESC, it.title ASC
            LIMIT 15
            """,
            (creature_id,),
        ).fetchall()

        quests = connection.execute(
            """
            SELECT q.title AS quest
            FROM quest_danger qd
            JOIN quest q ON q.article_id = qd.quest_id
            WHERE qd.creature_id = ?
            ORDER BY q.title ASC
            """,
            (creature_id,),
        ).fetchall()

        return {
            "entity": creature["title"],
            "match_type": match_type,
            "candidates": candidates,
            "data": {
                "title": creature["title"],
                "name": creature["name"],
                "hitpoints": creature["hitpoints"],
                "experience": creature["experience"],
                "armor": creature["armor"],
                "mitigation": creature.get("mitigation"),
                "speed": creature.get("speed"),
                "creature_class": creature.get("creature_class"),
                "location": creature.get("location"),
                "elemental_modifiers": {
                    "physical": creature.get("modifier_physical"),
                    "earth": creature.get("modifier_earth"),
                    "fire": creature.get("modifier_fire"),
                    "ice": creature.get("modifier_ice"),
                    "energy": creature.get("modifier_energy"),
                    "death": creature.get("modifier_death"),
                    "holy": creature.get("modifier_holy"),
                },
                "top_drops": [dict(d) for d in drops],
                "associated_quests": [q["quest"] for q in quests],
            },
            "snapshot_timestamp": snapshot_time,
            "article_timestamp": creature.get("timestamp"),
        }


def get_item_details(database_path: Path, raw_name: Any) -> dict[str, Any]:
    """Fetch structured item details combining item, attributes, NPC buyers, and sellers."""
    with closing(_connect_ro(database_path)) as connection:
        match_type, item, candidates = resolve_entity(connection, "item", raw_name)
        snapshot_time = get_snapshot_timestamp(connection)

        if item is None:
            return {
                "entity": raw_name if isinstance(raw_name, str) else "",
                "match_type": match_type,
                "candidates": candidates,
                "data": None,
                "snapshot_timestamp": snapshot_time,
                "article_timestamp": None,
            }

        item_id = item["article_id"]

        # Check if item_details view exists
        view_check = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'view' AND name = 'item_details'"
        ).fetchone()

        if view_check:
            details_row = connection.execute(
                "SELECT * FROM item_details WHERE article_id = ?",
                (item_id,),
            ).fetchone()
            details = dict(details_row) if details_row else dict(item)
        else:
            details = dict(item)

        # NPC buyers (players sell to them)
        buyers = connection.execute(
            """
            SELECT n.title AS npc, n.city, nob.value AS price
            FROM npc_offer_buy nob
            JOIN npc n ON n.article_id = nob.npc_id
            WHERE nob.item_id = ?
            ORDER BY nob.value DESC, n.title ASC
            LIMIT 5
            """,
            (item_id,),
        ).fetchall()

        # NPC sellers (players buy from them)
        sellers = connection.execute(
            """
            SELECT n.title AS npc, n.city, nos.value AS price
            FROM npc_offer_sell nos
            JOIN npc n ON n.article_id = nos.npc_id
            WHERE nos.item_id = ?
            ORDER BY nos.value ASC, n.title ASC
            LIMIT 5
            """,
            (item_id,),
        ).fetchall()

        # Quests where this item is a reward
        reward_quests = connection.execute(
            """
            SELECT q.title AS quest
            FROM quest_reward qr
            JOIN quest q ON q.article_id = qr.quest_id
            WHERE qr.item_id = ?
            ORDER BY q.title ASC
            """,
            (item_id,),
        ).fetchall()

        # Note: view defines required_level, fallback to level_required
        required_level = details.get("required_level") or details.get("level_required")

        return {
            "entity": item["title"],
            "match_type": match_type,
            "candidates": candidates,
            "data": {
                "title": item["title"],
                "name": item["name"],
                "attack": details.get("attack"),
                "defense": details.get("defense"),
                "defense_modifier": details.get("defense_modifier"),
                "armor": details.get("armor"),
                "weight": details.get("weight"),
                "item_class": details.get("item_class"),
                "item_type": details.get("item_type"),
                "level_required": required_level,
                "imbuement_slots": details.get("imbuement_slots"),
                "npc_buyers": [dict(b) for b in buyers],
                "npc_sellers": [dict(s) for s in sellers],
                "reward_from_quests": [q["quest"] for q in reward_quests],
            },
            "snapshot_timestamp": snapshot_time,
            "article_timestamp": item.get("timestamp"),
        }


def log_api_access(
    log_dir: Path,
    record: dict[str, Any],
) -> None:
    """Record an audit log entry. Does NOT record authentication tokens."""
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(log_dir, 0o700)
        log_file = log_dir / "api_access.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=True) + "\n")
        os.chmod(log_file, 0o600)
    except OSError:
        pass


def load_knowledge_payload(knowledge_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(knowledge_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise KnowledgeUnavailable(f"Knowledge corpus unavailable: {error}") from error

    documents = payload.get("documents") if isinstance(payload, dict) else None
    if not isinstance(documents, list) or not all(
        isinstance(document, dict)
        and isinstance(document.get("text"), str)
        and document.get("text")
        for document in documents
    ):
        raise KnowledgeUnavailable("Knowledge corpus has an invalid document structure.")
    return payload


class TibiaWikiRequestHandler(BaseHTTPRequestHandler):
    server_version = "GPTibiaHTTP/1.0"

    @property
    def application(self) -> "TibiaWikiHTTPServer":
        return self.server  # type: ignore[return-value]

    def do_GET(self) -> None:
        start_time = time.monotonic()
        request_id = str(uuid.uuid4())

        if self.path == "/v1/knowledge":
            if not self._is_authorized():
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "Unauthorized."})
                self._audit_log(request_id, "/v1/knowledge", start_time, HTTPStatus.UNAUTHORIZED, {})
                return
            try:
                payload = load_knowledge_payload(self.application.knowledge_path)
            except KnowledgeUnavailable as error:
                self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(error)})
                self._audit_log(request_id, "/v1/knowledge", start_time, HTTPStatus.SERVICE_UNAVAILABLE, {})
                return
            self._send_json(HTTPStatus.OK, payload)
            self._audit_log(
                request_id,
                "/v1/knowledge",
                start_time,
                HTTPStatus.OK,
                {},
                result_count=payload.get("document_count", 0),
            )
            return

        if self.path == "/health":
            try:
                document_count = load_knowledge_payload(
                    self.application.knowledge_path
                ).get("document_count", 0)
            except KnowledgeUnavailable:
                document_count = 0
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "healthy",
                    "service": "tibiawiki-http-api",
                    "database": self.application.database_path.name,
                    "knowledge_documents": document_count,
                },
            )
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_POST(self) -> None:
        start_time = time.monotonic()
        request_id = str(uuid.uuid4())

        if not self._is_authorized():
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "Unauthorized."})
            self._audit_log(request_id, self.path, start_time, HTTPStatus.UNAUTHORIZED, {})
            return

        try:
            body = self._read_json_body()
        except QueryRejected as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            self._audit_log(request_id, self.path, start_time, HTTPStatus.BAD_REQUEST, {})
            return
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body."})
            self._audit_log(request_id, self.path, start_time, HTTPStatus.BAD_REQUEST, {})
            return

        # Sanitize arguments for logging (never log token or sensitive fields)
        sanitized_args = {k: v for k, v in body.items() if k not in {"token", "auth", "password"}}

        if self.path == "/v1/query":
            try:
                result = execute_read_query(self.application.database_path, body.get("query"))
            except QueryRejected as error:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                self._audit_log(request_id, self.path, start_time, HTTPStatus.BAD_REQUEST, sanitized_args)
                return
            except sqlite3.Error as error:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"Query failed: {error}"})
                self._audit_log(request_id, self.path, start_time, HTTPStatus.BAD_REQUEST, sanitized_args)
                return

            self._send_json(HTTPStatus.OK, result)
            self._audit_log(
                request_id,
                self.path,
                start_time,
                HTTPStatus.OK,
                sanitized_args,
                result_count=result.get("count", 0),
            )
            return

        if self.path == "/v1/quest":
            name = body.get("name") or body.get("quest") or body.get("query")
            try:
                result = get_quest_overview(self.application.database_path, name)
            except sqlite3.Error as error:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"Quest query failed: {error}"})
                self._audit_log(request_id, self.path, start_time, HTTPStatus.BAD_REQUEST, sanitized_args)
                return

            self._send_json(HTTPStatus.OK, result)
            self._audit_log(
                request_id,
                self.path,
                start_time,
                HTTPStatus.OK,
                sanitized_args,
                entity_resolved=result.get("entity"),
                match_type=result.get("match_type"),
                result_count=1 if result.get("data") else 0,
            )
            return

        if self.path == "/v1/creature":
            name = body.get("name") or body.get("creature") or body.get("query")
            try:
                result = get_creature_profile(self.application.database_path, name)
            except sqlite3.Error as error:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"Creature query failed: {error}"})
                self._audit_log(request_id, self.path, start_time, HTTPStatus.BAD_REQUEST, sanitized_args)
                return

            self._send_json(HTTPStatus.OK, result)
            self._audit_log(
                request_id,
                self.path,
                start_time,
                HTTPStatus.OK,
                sanitized_args,
                entity_resolved=result.get("entity"),
                match_type=result.get("match_type"),
                result_count=1 if result.get("data") else 0,
            )
            return

        if self.path == "/v1/item":
            name = body.get("name") or body.get("item") or body.get("query")
            try:
                result = get_item_details(self.application.database_path, name)
            except sqlite3.Error as error:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"Item query failed: {error}"})
                self._audit_log(request_id, self.path, start_time, HTTPStatus.BAD_REQUEST, sanitized_args)
                return

            self._send_json(HTTPStatus.OK, result)
            self._audit_log(
                request_id,
                self.path,
                start_time,
                HTTPStatus.OK,
                sanitized_args,
                entity_resolved=result.get("entity"),
                match_type=result.get("match_type"),
                result_count=1 if result.get("data") else 0,
            )
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
        self._audit_log(request_id, self.path, start_time, HTTPStatus.NOT_FOUND, sanitized_args)

    def _audit_log(
        self,
        request_id: str,
        endpoint: str,
        start_time: float,
        status_code: HTTPStatus,
        arguments: dict[str, Any],
        entity_resolved: str | None = None,
        match_type: str | None = None,
        result_count: int = 0,
    ) -> None:
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        record = {
            "request_id": request_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "endpoint": endpoint,
            "duration_ms": duration_ms,
            "status_code": int(status_code),
            "arguments": arguments,
            "entity_resolved": entity_resolved,
            "match_type": match_type,
            "result_count": result_count,
        }
        log_api_access(self.application.log_dir, record)

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
        knowledge_path: Path,
        api_token: str,
        log_dir: Path | None = None,
    ) -> None:
        super().__init__(address, TibiaWikiRequestHandler)
        self.database_path = database_path
        self.knowledge_path = knowledge_path
        self.api_token = api_token
        self.log_dir = log_dir or (database_path.parent.parent / ".runtime")


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
    parser.add_argument(
        "--knowledge",
        type=Path,
        default=project_root / "data" / "rag_knowledge.json",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=project_root / ".runtime",
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
        args.knowledge.resolve(),
        read_api_token(args.token_file),
        args.log_dir.resolve(),
    )
    print(f"TibiaWiki HTTP API: http://{args.host}:{args.port}/v1/query")
    print(f"Quest Domain Tool:  http://{args.host}:{args.port}/v1/quest")
    print(f"Creature Domain:    http://{args.host}:{args.port}/v1/creature")
    print(f"Item Domain Tool:   http://{args.host}:{args.port}/v1/item")
    print(f"RAG knowledge:      http://{args.host}:{args.port}/v1/knowledge")
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
