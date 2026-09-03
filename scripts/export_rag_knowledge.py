#!/usr/bin/env python3

"""Export real TibiaWiki-SQL records as documents for the n8n RAG pipeline."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SOURCE_NAME = "tibiawiki-sql"


def _compact(values: Iterable[str | None]) -> list[str]:
    return [value.strip() for value in values if value and value.strip()]


def _csv(values: Iterable[str | None]) -> str:
    return ", ".join(_compact(values))


def _document(
    entity_type: str,
    article_id: int,
    title: str,
    lines: Iterable[str | None],
    timestamp: str | None,
) -> dict[str, Any]:
    text = "\n".join(_compact(lines))
    return {
        "id": f"{entity_type}:{article_id}",
        "text": text,
        "metadata": {
            "source": SOURCE_NAME,
            "entity_type": entity_type,
            "article_id": article_id,
            "title": title,
            "snapshot_timestamp": timestamp,
        },
    }


def _group_values(
    connection: sqlite3.Connection,
    query: str,
    value_builder: Any,
) -> dict[int, list[str]]:
    values: dict[int, list[str]] = defaultdict(list)
    for row in connection.execute(query):
        values[row[0]].append(value_builder(row))
    return values


def build_quest_documents(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    dangers = _group_values(
        connection,
        """
        SELECT qd.quest_id, c.title
        FROM quest_danger AS qd
        JOIN creature AS c ON c.article_id = qd.creature_id
        ORDER BY qd.quest_id, c.title
        """,
        lambda row: row[1],
    )
    rewards = _group_values(
        connection,
        """
        SELECT qr.quest_id, i.title
        FROM quest_reward AS qr
        JOIN item AS i ON i.article_id = qr.item_id
        ORDER BY qr.quest_id, i.title
        """,
        lambda row: row[1],
    )

    documents = []
    rows = connection.execute(
        """
        SELECT article_id, title, location, legend, level_required,
               level_recommended, active_time, estimated_time, is_premium,
               quest_log, timestamp
        FROM quest
        WHERE status = 'active'
        ORDER BY title
        """
    )
    for row in rows:
        premium = "sim" if row[8] else "nao"
        quest_log = "sim" if row[9] else "nao"
        documents.append(
            _document(
                "quest",
                row[0],
                row[1],
                [
                    "Tipo: quest.",
                    f"Nome: {row[1]}.",
                    f"Localizacao: {row[2]}." if row[2] else None,
                    f"Contexto: {row[3]}" if row[3] else None,
                    f"Level minimo: {row[4]}." if row[4] is not None else None,
                    f"Level recomendado: {row[5]}." if row[5] is not None else None,
                    f"Tempo ativo: {row[6]}." if row[6] else None,
                    f"Tempo estimado: {row[7]}." if row[7] else None,
                    f"Premium: {premium}. Quest log: {quest_log}.",
                    f"Perigos registrados: {_csv(dangers[row[0]])}."
                    if dangers[row[0]]
                    else None,
                    f"Recompensas registradas: {_csv(rewards[row[0]])}."
                    if rewards[row[0]]
                    else None,
                    "Limite da fonte: este snapshot nao contem o walkthrough completo da quest.",
                    "Fonte: snapshot comunitario da TibiaWiki gerado por tibiawiki-sql.",
                ],
                row[10],
            )
        )
    return documents


def build_creature_documents(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    abilities = _group_values(
        connection,
        """
        SELECT creature_id, name, effect, element
        FROM creature_ability
        ORDER BY creature_id, name
        """,
        lambda row: " - ".join(_compact([row[1], row[2], row[3]])),
    )
    documents = []
    rows = connection.execute(
        """
        SELECT article_id, title, hitpoints, experience, armor, mitigation,
               speed, creature_class, bestiary_class, bestiary_level,
               bestiary_occurrence, is_boss, runs_at, paralysable,
               sees_invisible, modifier_physical, modifier_earth,
               modifier_fire, modifier_ice, modifier_energy, modifier_death,
               modifier_holy, location, timestamp
        FROM creature
        WHERE status = 'active'
        ORDER BY title
        """
    )
    for row in rows:
        modifiers = (
            f"physical {row[15]}%, earth {row[16]}%, fire {row[17]}%, "
            f"ice {row[18]}%, energy {row[19]}%, death {row[20]}%, holy {row[21]}%"
        )
        documents.append(
            _document(
                "creature",
                row[0],
                row[1],
                [
                    "Tipo: criatura ou boss." if row[11] else "Tipo: criatura.",
                    f"Nome: {row[1]}.",
                    f"Classe: {_csv([row[7], row[8], row[9], row[10]])}."
                    if any(row[index] for index in (7, 8, 9, 10))
                    else None,
                    f"HP: {row[2]}. Experiencia: {row[3]}. Armor: {row[4]}. "
                    f"Mitigation: {row[5]}. Speed: {row[6]}.",
                    f"Modificadores de dano recebido: {modifiers}.",
                    f"Foge com {row[12]} HP." if row[12] else "Nao foge com HP baixo.",
                    f"Paralisavel: {'sim' if row[13] else 'nao'}. "
                    f"Enxerga invisivel: {'sim' if row[14] else 'nao'}.",
                    f"Localizacoes: {row[22]}" if row[22] else None,
                    f"Habilidades registradas: {'; '.join(abilities[row[0]])}."
                    if abilities[row[0]]
                    else None,
                    "Fonte: snapshot comunitario da TibiaWiki gerado por tibiawiki-sql.",
                ],
                row[23],
            )
        )
    return documents


def build_spell_documents(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    documents = []
    rows = connection.execute(
        """
        SELECT article_id, title, words, effect, spell_type, group_spell,
               element, level, mana, soul, is_premium, cooldown, knight,
               sorcerer, druid, paladin, monk, timestamp
        FROM spell
        WHERE status = 'active'
        ORDER BY title
        """
    )
    for row in rows:
        vocations = [
            name
            for name, enabled in zip(
                ["Knight", "Sorcerer", "Druid", "Paladin", "Monk"],
                row[12:17],
            )
            if enabled
        ]
        documents.append(
            _document(
                "spell",
                row[0],
                row[1],
                [
                    "Tipo: spell.",
                    f"Nome: {row[1]}. Palavras magicas: {row[2]}."
                    if row[2]
                    else f"Nome: {row[1]}.",
                    f"Efeito: {row[3]}" if row[3] else None,
                    f"Categoria: {_csv([row[4], row[5], row[6]])}."
                    if any(row[index] for index in (4, 5, 6))
                    else None,
                    f"Level: {row[7]}. Mana: {row[8]}. Soul: {row[9]}. "
                    f"Cooldown: {row[11]} segundos.",
                    f"Vocacoes: {_csv(vocations)}." if vocations else None,
                    f"Premium: {'sim' if row[10] else 'nao'}.",
                    "Fonte: snapshot comunitario da TibiaWiki gerado por tibiawiki-sql.",
                ],
                row[17],
            )
        )
    return documents


def build_imbuement_documents(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    materials = _group_values(
        connection,
        """
        SELECT im.imbuement_id, CAST(im.amount AS TEXT) || 'x ' || i.title
        FROM imbuement_material AS im
        JOIN item AS i ON i.article_id = im.item_id
        ORDER BY im.imbuement_id, i.title
        """,
        lambda row: row[1],
    )
    documents = []
    rows = connection.execute(
        """
        SELECT article_id, title, tier, type, category, effect, slots, timestamp
        FROM imbuement
        WHERE status = 'active'
        ORDER BY title
        """
    )
    for row in rows:
        documents.append(
            _document(
                "imbuement",
                row[0],
                row[1],
                [
                    "Tipo: imbuement.",
                    f"Nome: {row[1]}. Tier: {row[2]}. Tipo: {row[3]}.",
                    f"Categoria: {row[4]}. Efeito: {row[5]}."
                    if row[5]
                    else f"Categoria: {row[4]}.",
                    f"Slots compativeis: {row[6]}." if row[6] else None,
                    f"Materiais: {_csv(materials[row[0]])}." if materials[row[0]] else None,
                    "Fonte: snapshot comunitario da TibiaWiki gerado por tibiawiki-sql.",
                ],
                row[7],
            )
        )
    return documents


def build_knowledge_payload(database_path: Path) -> dict[str, Any]:
    database_uri = f"{database_path.resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(database_uri, uri=True)) as connection:
        documents = [
            *build_quest_documents(connection),
            *build_creature_documents(connection),
            *build_spell_documents(connection),
            *build_imbuement_documents(connection),
        ]

    counts: dict[str, int] = defaultdict(int)
    for document in documents:
        counts[document["metadata"]["entity_type"]] += 1

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE_NAME,
        "document_count": len(documents),
        "counts": dict(sorted(counts.items())),
        "documents": documents,
    }


def write_knowledge_payload(database_path: Path, output_path: Path) -> dict[str, Any]:
    payload = build_knowledge_payload(database_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    try:
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return payload


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("database", nargs="?", type=Path, default=project_root / "data" / "tibiawiki.db")
    parser.add_argument("--output", type=Path, default=project_root / "data" / "rag_knowledge.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.database.is_file():
        raise SystemExit(f"Database not found: {args.database}")
    payload = write_knowledge_payload(args.database, args.output)
    print(f"RAG knowledge exported: {args.output} ({payload['document_count']} documents)")
    print(json.dumps(payload["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
