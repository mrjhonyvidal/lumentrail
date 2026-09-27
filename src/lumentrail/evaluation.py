"""Deterministic retrieval metrics; answer claims need separate human review."""

from __future__ import annotations

import sqlite3

from .embedding import Embedder
from .retrieval import search


def evaluate(connection: sqlite3.Connection, judgements: list[dict], embedder: Embedder, *, method: str, limit: int) -> dict:
    labelled = [case for case in judgements if case.get("relevant_ids")]
    if not labelled:
        raise ValueError("No reviewed relevance labels found. HealthSearchQA questions alone are not an eval set")
    recall = 0.0
    reciprocal_rank = 0.0
    precision = 0.0
    cases = []
    for case in labelled:
        hits = search(connection, case["question"], embedder, method=method, limit=limit)
        retrieved = [hit["id"] for hit in hits]
        relevant = set(case["relevant_ids"])
        found = relevant.intersection(retrieved)
        recall += len(found) / len(relevant)
        precision += len(found) / limit
        reciprocal_rank += next((1 / (position + 1) for position, passage_id in enumerate(retrieved)
                                 if passage_id in relevant), 0.0)
        cases.append({"question": case["question"], "expected": sorted(relevant), "retrieved": retrieved})
    count = len(labelled)
    return {"method": method, "questions": count, "k": limit,
            "recall_at_k": round(recall / count, 4),
            "precision_at_k": round(precision / count, 4),
            "mean_reciprocal_rank": round(reciprocal_rank / count, 4),
            "cases": cases}

