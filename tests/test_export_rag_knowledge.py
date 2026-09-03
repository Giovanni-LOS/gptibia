from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "export_rag_knowledge.py"
SPEC = importlib.util.spec_from_file_location("export_rag_knowledge", MODULE_PATH)
assert SPEC and SPEC.loader
EXPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORTER)


class ExportRAGKnowledgeTest(unittest.TestCase):
    def test_exports_supported_entities_with_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.db"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE quest (
                        article_id INTEGER, title TEXT, location TEXT, legend TEXT,
                        level_required INTEGER, level_recommended INTEGER,
                        active_time TEXT, estimated_time TEXT, is_premium INTEGER,
                        quest_log INTEGER, status TEXT, timestamp TEXT
                    );
                    CREATE TABLE quest_danger (quest_id INTEGER, creature_id INTEGER);
                    CREATE TABLE quest_reward (quest_id INTEGER, item_id INTEGER);
                    CREATE TABLE item (article_id INTEGER, title TEXT);
                    CREATE TABLE creature (
                        article_id INTEGER, title TEXT, hitpoints INTEGER,
                        experience INTEGER, armor INTEGER, mitigation REAL,
                        speed INTEGER, creature_class TEXT, bestiary_class TEXT,
                        bestiary_level TEXT, bestiary_occurrence TEXT,
                        is_boss INTEGER, runs_at INTEGER, paralysable INTEGER,
                        sees_invisible INTEGER, modifier_physical INTEGER,
                        modifier_earth INTEGER, modifier_fire INTEGER,
                        modifier_ice INTEGER, modifier_energy INTEGER,
                        modifier_death INTEGER, modifier_holy INTEGER,
                        location TEXT, status TEXT, timestamp TEXT
                    );
                    CREATE TABLE creature_ability (
                        creature_id INTEGER, name TEXT, effect TEXT, element TEXT
                    );
                    CREATE TABLE spell (
                        article_id INTEGER, title TEXT, words TEXT, effect TEXT,
                        spell_type TEXT, group_spell TEXT, element TEXT,
                        level INTEGER, mana INTEGER, soul INTEGER,
                        is_premium INTEGER, cooldown INTEGER, knight INTEGER,
                        sorcerer INTEGER, druid INTEGER, paladin INTEGER,
                        monk INTEGER, status TEXT, timestamp TEXT
                    );
                    CREATE TABLE imbuement (
                        article_id INTEGER, title TEXT, tier TEXT, type TEXT,
                        category TEXT, effect TEXT, slots TEXT, status TEXT,
                        timestamp TEXT
                    );
                    CREATE TABLE imbuement_material (
                        imbuement_id INTEGER, item_id INTEGER, amount INTEGER
                    );

                    INSERT INTO item VALUES (10, 'Ankh');
                    INSERT INTO item VALUES (11, 'Fiery Heart');
                    INSERT INTO creature VALUES (
                        2, 'Demon', 8200, 6000, 44, 2.76, 128, 'Demons',
                        'Demon', 'Hard', 'Common', 0, 0, 1, 1, 75, 60, 0,
                        112, 50, 80, 112, 'Goroma', 'active', '2026-01-01'
                    );
                    INSERT INTO creature_ability VALUES (2, 'Melee', 'Physical hit', 'Physical');
                    INSERT INTO quest VALUES (
                        1, 'Desert Quest', 'Jakundaf', 'Ancient secret', 20, 20,
                        NULL, NULL, 0, 1, 'active', '2026-01-01'
                    );
                    INSERT INTO quest_danger VALUES (1, 2);
                    INSERT INTO quest_reward VALUES (1, 10);
                    INSERT INTO spell VALUES (
                        3, 'Light', 'utevo lux', 'Creates light', 'Instant',
                        'Support', NULL, 8, 20, 0, 0, 2, 1, 1, 1, 1, 1,
                        'active', '2026-01-01'
                    );
                    INSERT INTO imbuement VALUES (
                        4, 'Powerful Scorch', 'Powerful', 'Scorch', 'Fire Damage',
                        'Fire damage 50%', 'swords', 'active', '2026-01-01'
                    );
                    INSERT INTO imbuement_material VALUES (4, 11, 5);
                    """
                )
                connection.commit()

            payload = EXPORTER.build_knowledge_payload(database_path)

            self.assertEqual(payload["document_count"], 4)
            self.assertEqual(
                payload["counts"],
                {"creature": 1, "imbuement": 1, "quest": 1, "spell": 1},
            )
            quest = next(document for document in payload["documents"] if document["id"] == "quest:1")
            self.assertIn("Perigos registrados: Demon", quest["text"])
            self.assertIn("Recompensas registradas: Ankh", quest["text"])
            self.assertEqual(quest["metadata"]["source"], "tibiawiki-sql")


if __name__ == "__main__":
    unittest.main()
