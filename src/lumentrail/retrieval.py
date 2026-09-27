"""Retrieval, rank fusion and optional reranking for a public-data lab."""

from __future__ import annotations

import json
import sqlite3

from .embedding import Embedder
from .storage import all_passages, keyword_search


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def reciprocal_rank_fusion(rankings: list[list[str]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for position, passage_id in enumerate(ranking, start=1):
            scores[passage_id] = scores.get(passage_id, 0.0) + 1 / (60 + position)
    return scores


def search(
    connection: sqlite3.Connection,
    question: str,
    embedder: Embedder,
    *,
    method: str = "hybrid",
    limit: int = 3,
    rerank: bool = False,
    expand_entities: bool = False,
) -> list[dict]:
    if method not in {"keyword", "dense", "hybrid"}:
        raise ValueError("Method must be keyword, dense or hybrid")
    if not question.strip() or limit < 1 or limit > 20:
        raise ValueError("Use a non-empty question and a limit from 1 to 20")
    passages = all_passages(connection)
    if not passages:
        return []
    if any(passage["embedding_model"] != embedder.name for passage in passages):
        raise ValueError("Embedding model changed. Re-ingest the collection with the selected model")
    by_id = {passage["id"]: passage for passage in passages}
    candidate_limit = min(len(passages), max(20, limit * 5))
    rankings: list[list[str]] = []
    if method in {"keyword", "hybrid"}:
        rankings.append(keyword_search(connection, question, candidate_limit))
    if method in {"dense", "hybrid"}:
        query_vector = embedder.encode([question], queries=True)[0]
        dense = sorted(
            passages,
            key=lambda passage: cosine(query_vector, json.loads(passage["embedding"])),
            reverse=True,
        )
        rankings.append([passage["id"] for passage in dense[:candidate_limit]])
    scores = reciprocal_rank_fusion(rankings)
    if expand_entities:
        seeds = sorted(scores, key=lambda passage_id: (-scores[passage_id], passage_id))[:3]
        matched = {entity.lower() for passage_id in seeds
                   for entity in json.loads(by_id[passage_id]["entities"])}
        for passage in passages:
            if any(entity.lower() in matched for entity in json.loads(passage["entities"])):
                scores.setdefault(passage["id"], 1 / 120)
    ordered_ids = sorted(scores, key=lambda passage_id: (-scores[passage_id], passage_id))[:candidate_limit]
    if rerank and ordered_ids:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as error:
            raise RuntimeError("Install model support: pip install -e '.[models]'") from error
        model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L6-v2", trust_remote_code=False)
        pairs = [(question, f'{by_id[passage_id]["question"]} {by_id[passage_id]["answer"]}')
                 for passage_id in ordered_ids]
        rerank_scores = model.predict(pairs)
        ordered_ids = [passage_id for _, passage_id in sorted(zip(rerank_scores, ordered_ids), reverse=True)]
    return [
        {"id": passage_id, "question": by_id[passage_id]["question"],
         "answer": by_id[passage_id]["answer"], "source": by_id[passage_id]["source"],
         "score": round(scores[passage_id], 6)}
        for passage_id in ordered_ids[:limit]
    ]
