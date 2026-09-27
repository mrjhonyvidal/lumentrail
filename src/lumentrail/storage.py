"""SQLite persistence with an FTS5 keyword index and exact vector scan."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from .embedding import tokens

SEARCH_STOPWORDS = {"a", "an", "and", "are", "can", "do", "does", "for", "how", "i", "in", "is", "of", "the", "to", "what", "when", "with"}


def connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS passages (
            id TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            source TEXT NOT NULL,
            entities TEXT NOT NULL,
            embedding TEXT NOT NULL,
            embedding_model TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS passage_search
            USING fts5(id UNINDEXED, content, tokenize='porter unicode61');
        CREATE TABLE IF NOT EXISTS memory_events (
            id INTEGER PRIMARY KEY,
            person TEXT NOT NULL,
            note TEXT NOT NULL,
            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            valid_at TEXT NOT NULL,
            expires_at TEXT
        );
    """)
    if os.name == "posix":
        os.chmod(database_path, 0o600)
    return connection


def replace_passages(connection: sqlite3.Connection, passages: list[dict], embeddings: list[list[float]], model: str) -> None:
    if len(passages) != len(embeddings):
        raise ValueError("Each passage needs exactly one embedding")
    with connection:
        connection.execute("DELETE FROM passage_search")
        connection.execute("DELETE FROM passages")
        for passage, embedding in zip(passages, embeddings):
            connection.execute(
                "INSERT INTO passages VALUES (?, ?, ?, ?, ?, ?, ?)",
                (passage["id"], passage["question"], passage["answer"], passage["source"],
                 json.dumps(passage.get("entities", [])), json.dumps(embedding), model),
            )
            connection.execute(
                "INSERT INTO passage_search (id, content) VALUES (?, ?)",
                (passage["id"], f'{passage["question"]} {passage["answer"]}'),
            )


def all_passages(connection: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in connection.execute("SELECT * FROM passages ORDER BY id")]


def keyword_search(connection: sqlite3.Connection, question: str, limit: int) -> list[str]:
    words = [word for word in dict.fromkeys(tokens(question)) if word not in SEARCH_STOPWORDS][:20]
    if not words:
        return []
    expression = " OR ".join(f'"{word}"' for word in words)
    rows = connection.execute(
        "SELECT id FROM passage_search WHERE passage_search MATCH ? ORDER BY bm25(passage_search) LIMIT ?",
        (expression, limit),
    )
    return [row["id"] for row in rows]
