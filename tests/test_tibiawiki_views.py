from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "create_tibiawiki_views.py"
SPEC = importlib.util.spec_from_file_location("create_tibiawiki_views", MODULE_PATH)
assert SPEC and SPEC.loader
VIEWS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VIEWS)


class TibiaWikiViewsTest(unittest.TestCase):
    def test_item_details_combines_base_fields_and_attributes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.db"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    """
                    CREATE TABLE item (
                        article_id INTEGER PRIMARY KEY,
                        title TEXT,
                        name TEXT,
                        weight REAL,
                        item_class TEXT,
                        item_type TEXT,
                        type_secondary TEXT,
                        value_buy INTEGER,
                        value_sell INTEGER
                    )
                    """
                )
                connection.execute(
                    "CREATE TABLE item_attribute (item_id INTEGER, name TEXT, value TEXT)"
                )
                connection.execute(
                    "INSERT INTO item VALUES (1, 'Magic Sword', 'Magic Sword', 42.0, "
                    "'Weapons', 'Sword Weapons', NULL, 0, 350)"
                )
                connection.executemany(
                    "INSERT INTO item_attribute VALUES (1, ?, ?)",
                    [("attack", "48"), ("defense", "35"), ("defense_modifier", "+3")],
                )
                connection.commit()

            VIEWS.create_views(database_path)

            with closing(sqlite3.connect(database_path)) as connection:
                row = connection.execute(
                    "SELECT attack, defense, defense_modifier, weight "
                    "FROM item_details WHERE title = 'Magic Sword'"
                ).fetchone()

            self.assertEqual(row, ("48", "35", "+3", 42.0))


if __name__ == "__main__":
    unittest.main()
