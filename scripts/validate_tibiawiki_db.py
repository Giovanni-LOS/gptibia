#!/usr/bin/env python3

"""Validate the generated TibiaWiki SQLite database without modifying it."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from contextlib import closing
from pathlib import Path


REQUIRED_TABLES = (
    "creature",
    "creature_drop",
    "imbuement",
    "item",
    "npc",
    "quest",
    "spell",
)
REQUIRED_VIEWS = ("item_details",)


def validate(database_path: Path) -> int:
    if not database_path.is_file():
        print(f"Database not found: {database_path}", file=sys.stderr)
        return 1

    database_uri = f"{database_path.resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(database_uri, uri=True)) as connection:
        integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
        if integrity != "ok":
            print(f"SQLite quick_check failed: {integrity}", file=sys.stderr)
            return 1

        available_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        missing_tables = sorted(set(REQUIRED_TABLES) - available_tables)
        if missing_tables:
            print(
                f"Missing required tables: {', '.join(missing_tables)}",
                file=sys.stderr,
            )
            return 1

        available_views = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'view'"
            )
        }
        missing_views = sorted(set(REQUIRED_VIEWS) - available_views)
        if missing_views:
            print(
                f"Missing required views: {', '.join(missing_views)}",
                file=sys.stderr,
            )
            return 1

        print("SQLite quick_check: ok")
        for table in REQUIRED_TABLES:
            row_count = connection.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]
            if row_count == 0:
                print(f"Required table is empty: {table}", file=sys.stderr)
                return 1
            print(f"{table}: {row_count} rows")

        for view in REQUIRED_VIEWS:
            row_count = connection.execute(
                f'SELECT COUNT(*) FROM "{view}"'
            ).fetchone()[0]
            if row_count == 0:
                print(f"Required view is empty: {view}", file=sys.stderr)
                return 1
            print(f"{view}: {row_count} rows")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    return validate(args.database)


if __name__ == "__main__":
    raise SystemExit(main())
