#!/usr/bin/env python3

"""Create stable semantic views on top of the generated TibiaWiki schema."""

from __future__ import annotations

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path


ITEM_DETAILS_VIEW = """
CREATE VIEW item_details AS
SELECT
    i.article_id,
    i.title,
    i.name,
    i.weight,
    i.item_class,
    i.item_type,
    i.type_secondary,
    i.value_buy,
    i.value_sell,
    MAX(CASE WHEN ia.name = 'attack' THEN ia.value END) AS attack,
    MAX(CASE WHEN ia.name = 'attack_extra' THEN ia.value END) AS attack_extra,
    MAX(CASE WHEN ia.name = 'attack_fire' THEN ia.value END) AS attack_fire,
    MAX(CASE WHEN ia.name = 'attack_earth' THEN ia.value END) AS attack_earth,
    MAX(CASE WHEN ia.name = 'attack_energy' THEN ia.value END) AS attack_energy,
    MAX(CASE WHEN ia.name = 'attack_ice' THEN ia.value END) AS attack_ice,
    MAX(CASE WHEN ia.name = 'attack_death' THEN ia.value END) AS attack_death,
    MAX(CASE WHEN ia.name = 'defense' THEN ia.value END) AS defense,
    MAX(CASE WHEN ia.name = 'defense_modifier' THEN ia.value END) AS defense_modifier,
    MAX(CASE WHEN ia.name = 'armor' THEN ia.value END) AS armor,
    MAX(CASE WHEN ia.name = 'weapon_type' THEN ia.value END) AS weapon_type,
    MAX(CASE WHEN ia.name = 'hands' THEN ia.value END) AS hands,
    MAX(CASE WHEN ia.name = 'range' THEN ia.value END) AS range,
    MAX(CASE WHEN ia.name = 'required_level' THEN ia.value END) AS required_level,
    MAX(CASE WHEN ia.name = 'required_magic_level' THEN ia.value END) AS required_magic_level,
    MAX(CASE WHEN ia.name = 'required_vocation' THEN ia.value END) AS required_vocation,
    MAX(CASE WHEN ia.name = 'imbuement_slots' THEN ia.value END) AS imbuement_slots,
    MAX(CASE WHEN ia.name = 'resistance_physical' THEN ia.value END) AS resistance_physical,
    MAX(CASE WHEN ia.name = 'resistance_fire' THEN ia.value END) AS resistance_fire,
    MAX(CASE WHEN ia.name = 'resistance_earth' THEN ia.value END) AS resistance_earth,
    MAX(CASE WHEN ia.name = 'resistance_energy' THEN ia.value END) AS resistance_energy,
    MAX(CASE WHEN ia.name = 'resistance_ice' THEN ia.value END) AS resistance_ice,
    MAX(CASE WHEN ia.name = 'resistance_death' THEN ia.value END) AS resistance_death,
    MAX(CASE WHEN ia.name = 'resistance_holy' THEN ia.value END) AS resistance_holy
FROM item AS i
LEFT JOIN item_attribute AS ia ON ia.item_id = i.article_id
GROUP BY i.article_id
"""


def create_views(database_path: Path) -> None:
    with closing(sqlite3.connect(database_path)) as connection:
        existing = connection.execute(
            "SELECT type FROM sqlite_master WHERE name = 'item_details'"
        ).fetchone()
        if existing and existing[0] != "view":
            raise RuntimeError("item_details exists but is not a view")

        connection.execute("DROP VIEW IF EXISTS item_details")
        connection.execute(ITEM_DETAILS_VIEW)
        connection.commit()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    create_views(args.database)
    print("Semantic view created: item_details")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
