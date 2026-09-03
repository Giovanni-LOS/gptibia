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
        self.log_dir = Path(self.temporary_directory.name) / "logs"

        with closing(sqlite3.connect(self.database)) as connection:
            # Create core tables
            connection.execute(
                """
                CREATE TABLE database_info (
                    key TEXT,
                    value TEXT
                )
                """
            )
            connection.execute(
                """
                INSERT INTO database_info VALUES
                ('generate_time', '2026-09-01T20:17:14.418357+00:00'),
                ('version', '9.0.0')
                """
            )
            connection.execute(
                """
                CREATE TABLE creature (
                    article_id INTEGER PRIMARY KEY,
                    title TEXT,
                    name TEXT,
                    hitpoints INTEGER,
                    experience INTEGER,
                    armor INTEGER,
                    mitigation REAL,
                    speed INTEGER,
                    creature_class TEXT,
                    location TEXT,
                    modifier_physical INTEGER,
                    modifier_earth INTEGER,
                    modifier_fire INTEGER,
                    modifier_ice INTEGER,
                    modifier_energy INTEGER,
                    modifier_death INTEGER,
                    modifier_holy INTEGER,
                    timestamp TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE quest (
                    article_id INTEGER PRIMARY KEY,
                    title TEXT,
                    name TEXT,
                    location TEXT,
                    level_required INTEGER,
                    level_recommended INTEGER,
                    is_premium INTEGER,
                    quest_log TEXT,
                    legend TEXT,
                    timestamp TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE item (
                    article_id INTEGER PRIMARY KEY,
                    title TEXT,
                    name TEXT,
                    weight REAL,
                    item_class TEXT,
                    item_type TEXT,
                    timestamp TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE item_attribute (
                    item_id INTEGER,
                    name TEXT,
                    value TEXT
                )
                """
            )
            # Match real production view (create_tibiawiki_views.py: required_level)
            connection.execute(
                """
                CREATE VIEW item_details AS
                SELECT
                    i.article_id,
                    i.title,
                    i.name,
                    i.weight,
                    i.item_class,
                    i.item_type,
                    i.timestamp,
                    att.value AS attack,
                    def.value AS defense,
                    def_mod.value AS defense_modifier,
                    arm.value AS armor,
                    req.value AS required_level,
                    slots.value AS imbuement_slots
                FROM item i
                LEFT JOIN item_attribute att ON att.item_id = i.article_id AND att.name = 'attack'
                LEFT JOIN item_attribute def ON def.item_id = i.article_id AND def.name = 'defense'
                LEFT JOIN item_attribute def_mod ON def_mod.item_id = i.article_id AND def_mod.name = 'defense_modifier'
                LEFT JOIN item_attribute arm ON arm.item_id = i.article_id AND arm.name = 'armor'
                LEFT JOIN item_attribute req ON req.item_id = i.article_id AND req.name = 'required_level'
                LEFT JOIN item_attribute slots ON slots.item_id = i.article_id AND slots.name = 'imbuement_slots'
                """
            )
            connection.execute(
                """
                CREATE TABLE quest_danger (
                    quest_id INTEGER,
                    creature_id INTEGER
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE quest_reward (
                    quest_id INTEGER,
                    item_id INTEGER
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE creature_drop (
                    creature_id INTEGER,
                    item_id INTEGER,
                    chance REAL,
                    min INTEGER,
                    max INTEGER
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE npc (
                    article_id INTEGER PRIMARY KEY,
                    title TEXT,
                    name TEXT,
                    city TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE npc_offer_buy (
                    npc_id INTEGER,
                    item_id INTEGER,
                    value INTEGER,
                    currency_id INTEGER
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE npc_offer_sell (
                    npc_id INTEGER,
                    item_id INTEGER,
                    value INTEGER,
                    currency_id INTEGER
                )
                """
            )

            # Insert sample data: Annihilator, Angry Demon, Magic Sword, Annihilation Bear
            connection.execute(
                """
                INSERT INTO quest VALUES
                (2520, 'The Annihilator Quest', 'the annihilator quest', 'Edron Hero Cave.', 100, 130, 1, 'Log text', 'Legend', '2025-02-11T11:04:54+00:00')
                """
            )
            connection.execute(
                """
                INSERT INTO creature VALUES
                (1176, 'Demon', 'demon', 8200, 6000, 44, 1.0, 110, 'Demons', 'Hell', 75, 60, 0, 112, 50, 80, 112, '2025-02-11T11:04:54+00:00'),
                (1500, 'Angry Demon', 'angry demon', 8200, 6000, 40, 1.0, 120, 'Demons', 'Annihilator Room', 75, 60, 0, 112, 50, 80, 112, '2025-02-11T11:04:54+00:00')
                """
            )
            connection.execute(
                """
                INSERT INTO item VALUES
                (101, 'Magic Sword', 'magic sword', 42.0, 'Weapons', 'Sword', '2025-12-08T14:27:08+00:00'),
                (102, 'Annihilation Bear', 'annihilation bear', 4.5, 'Other', 'Doll', '2025-12-08T14:27:08+00:00')
                """
            )
            connection.executemany(
                "INSERT INTO item_attribute VALUES (?, ?, ?)",
                [
                    (101, "attack", "48"),
                    (101, "defense", "35"),
                    (101, "defense_modifier", "+3"),
                    (101, "required_level", "80"),
                    (101, "imbuement_slots", "2"),
                ],
            )
            connection.execute("INSERT INTO quest_danger VALUES (2520, 1500)")
            connection.executemany(
                "INSERT INTO quest_reward VALUES (?, ?)",
                [(2520, 101), (2520, 102)],
            )
            connection.execute("INSERT INTO creature_drop VALUES (1176, 101, 0.05, 1, 1)")
            connection.execute("INSERT INTO npc VALUES (1, 'H.L.', 'h.l.', 'Venore')")
            connection.execute("INSERT INTO npc_offer_buy VALUES (1, 101, 350, 0)")

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

    def test_quest_overview_partial_resolution_and_relations(self) -> None:
        result = API.get_quest_overview(self.database, "Annihilator")
        self.assertEqual(result["entity"], "The Annihilator Quest")
        self.assertEqual(result["match_type"], "partial")
        self.assertIsNotNone(result["data"])
        self.assertEqual(result["data"]["level_required"], 100)
        self.assertEqual(result["snapshot_timestamp"], "2026-09-01T20:17:14.418357+00:00")
        self.assertEqual(result["article_timestamp"], "2025-02-11T11:04:54+00:00")

        # Danger must include Angry Demon
        dangers = [d["name"] for d in result["data"]["dangers"]]
        self.assertIn("Angry Demon", dangers)

        # Rewards must include Magic Sword and Annihilation Bear
        rewards = result["data"]["rewards"]
        self.assertIn("Magic Sword", rewards)
        self.assertIn("Annihilation Bear", rewards)

    def test_quest_overview_fuzzy_resolution_for_typo(self) -> None:
        # Resolving "anihillation" typo from chat log
        result = API.get_quest_overview(self.database, "anihillation")
        self.assertEqual(result["entity"], "The Annihilator Quest")
        self.assertEqual(result["match_type"], "fuzzy")
        self.assertIsNotNone(result["data"])
        self.assertIn("Angry Demon", [d["name"] for d in result["data"]["dangers"]])
        self.assertIn("Annihilation Bear", result["data"]["rewards"])

    def test_quest_overview_not_found(self) -> None:
        result = API.get_quest_overview(self.database, "NonExistentQuestXYZ")
        self.assertEqual(result["match_type"], "not_found")
        self.assertIsNone(result["data"])

    def test_creature_profile_demon_and_drops(self) -> None:
        result = API.get_creature_profile(self.database, "Demon")
        self.assertEqual(result["entity"], "Demon")
        self.assertEqual(result["match_type"], "exact")
        self.assertIsNotNone(result["data"])
        self.assertEqual(result["data"]["hitpoints"], 8200)
        self.assertEqual(result["data"]["elemental_modifiers"]["ice"], 112)
        self.assertEqual(result["data"]["elemental_modifiers"]["fire"], 0)

        # Drop check
        drops = [d["item"] for d in result["data"]["top_drops"]]
        self.assertIn("Magic Sword", drops)

    def test_item_details_magic_sword_with_required_level_and_npc(self) -> None:
        result = API.get_item_details(self.database, "Magic Sword")
        self.assertEqual(result["entity"], "Magic Sword")
        self.assertEqual(result["match_type"], "exact")
        self.assertIsNotNone(result["data"])
        self.assertEqual(result["data"]["attack"], "48")
        self.assertEqual(result["data"]["defense"], "35")
        self.assertEqual(result["data"]["defense_modifier"], "+3")
        self.assertEqual(result["data"]["level_required"], "80")
        self.assertEqual(result["data"]["weight"], 42.0)

        # Economic relations (H.L. buying in Venore for 350 gp)
        buyers = result["data"]["npc_buyers"]
        self.assertEqual(len(buyers), 1)
        self.assertEqual(buyers[0]["npc"], "H.L.")
        self.assertEqual(buyers[0]["price"], 350)

        # Quest reward linkage
        self.assertIn("The Annihilator Quest", result["data"]["reward_from_quests"])

    def test_audit_logging_does_not_leak_bearer_token(self) -> None:
        API.log_api_access(
            self.log_dir,
            {
                "request_id": "req-123",
                "endpoint": "/v1/quest",
                "arguments": {"name": "Annihilator"},
                "status_code": 200,
            },
        )
        log_file = self.log_dir / "api_access.log"
        self.assertTrue(log_file.is_file())
        content = log_file.read_text(encoding="utf-8")
        self.assertIn("req-123", content)
        self.assertIn("/v1/quest", content)
        self.assertNotIn("Bearer", content)
        self.assertNotIn("token", content)

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
