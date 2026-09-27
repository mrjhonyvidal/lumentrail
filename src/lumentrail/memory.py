"""Opt-in local, user-scoped temporal notes for synthetic experiments."""

from __future__ import annotations

import sqlite3
from datetime import date


def add_note(connection: sqlite3.Connection, person: str, note: str, valid_at: str, expires_at: str | None) -> int:
    if not person.strip() or not note.strip():
        raise ValueError("Person and note must not be empty")
    date.fromisoformat(valid_at)
    if expires_at:
        date.fromisoformat(expires_at)
        if expires_at < valid_at:
            raise ValueError("Expiry must follow the event date")
    with connection:
        cursor = connection.execute(
            "INSERT INTO memory_events (person, note, valid_at, expires_at) VALUES (?, ?, ?, ?)",
            (person, note, valid_at, expires_at),
        )
    return cursor.lastrowid


def list_notes(connection: sqlite3.Connection, person: str, as_of: str) -> list[dict]:
    date.fromisoformat(as_of)
    return [dict(row) for row in connection.execute(
        "SELECT id, note, recorded_at, valid_at, expires_at FROM memory_events "
        "WHERE person = ? AND valid_at <= ? AND (expires_at IS NULL OR expires_at >= ?) "
        "ORDER BY valid_at DESC, id DESC", (person, as_of, as_of),
    )]


def delete_notes(connection: sqlite3.Connection, person: str) -> int:
    with connection:
        cursor = connection.execute("DELETE FROM memory_events WHERE person = ?", (person,))
    return cursor.rowcount

