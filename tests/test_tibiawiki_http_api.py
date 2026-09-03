from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "tibiawiki_http_api.py"
SPEC = importlib.util.spec_from_file_location("tibiawiki_http_api", MODULE_PATH)
assert SPEC and SPEC.loader
API = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(API)


class TibiaWikiHTTPAPITest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "test.db"
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("CREATE TABLE creature (title TEXT, hitpoints INTEGER)")
            connection.executemany(
                "INSERT INTO creature VALUES (?, ?)",
                [("Demon", 8200), ("Dragon", 1000)],
            )
            connection.commit()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_select_returns_rows(self) -> None:
        result = API.execute_read_query(
            self.database,
            "SELECT title, hitpoints FROM creature WHERE title = 'Demon'",
        )
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["rows"][0]["hitpoints"], 8200)
        self.assertFalse(result["truncated"])

    def test_write_is_rejected(self) -> None:
        with self.assertRaisesRegex(API.QueryRejected, "Only SELECT"):
            API.execute_read_query(self.database, "DELETE FROM creature")

    def test_multiple_statements_are_rejected(self) -> None:
        with self.assertRaisesRegex(API.QueryRejected, "one SQL statement"):
            API.execute_read_query(self.database, "SELECT 1; SELECT 2")

    def test_result_is_limited_by_server(self) -> None:
        query = (
            "SELECT creature.title FROM creature "
            "CROSS JOIN creature AS c2 CROSS JOIN creature AS c3 "
            "CROSS JOIN creature AS c4 CROSS JOIN creature AS c5"
        )
        result = API.execute_read_query(self.database, query)
        self.assertEqual(result["count"], API.MAX_ROWS)
        self.assertTrue(result["truncated"])

    def test_load_knowledge_payload_validates_documents(self) -> None:
        knowledge_path = Path(self.temporary_directory.name) / "knowledge.json"
        knowledge_path.write_text(
            json.dumps(
                {
                    "document_count": 1,
                    "documents": [{"id": "quest:1", "text": "Real quest data"}],
                }
            ),
            encoding="utf-8",
        )

        payload = API.load_knowledge_payload(knowledge_path)

        self.assertEqual(payload["document_count"], 1)

    def test_invalid_knowledge_payload_is_rejected(self) -> None:
        knowledge_path = Path(self.temporary_directory.name) / "knowledge.json"
        knowledge_path.write_text('{"documents": [{"text": ""}]}', encoding="utf-8")

        with self.assertRaises(API.KnowledgeUnavailable):
            API.load_knowledge_payload(knowledge_path)


if __name__ == "__main__":
    unittest.main()
