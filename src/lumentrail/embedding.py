"""Small offline baseline and an optional real sentence embedding model."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def tokens(text: str) -> list[str]:
    return [match.group().lower() for match in TOKEN_PATTERN.finditer(text)]


def normalise(values: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in values))
    return [value / length for value in values] if length else values


class Embedder(Protocol):
    name: str

    def encode(self, texts: list[str], *, queries: bool = False) -> list[list[float]]: ...


class HashEmbedder:
    """Deterministic word hashing for offline plumbing tests, not semantic search."""

    name = "hash-v1-256"

    def encode(self, texts: list[str], *, queries: bool = False) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * 256
            for token in tokens(text):
                digest = hashlib.sha256(token.encode()).digest()
                position = int.from_bytes(digest[:2], "big") % len(vector)
                vector[position] += 1 if digest[2] % 2 else -1
            vectors.append(normalise(vector))
        return vectors


class BgeEmbedder:
    name = "BAAI/bge-small-en-v1.5"

    def __init__(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError("Install model support: pip install -e '.[models]'") from error
        self.model = SentenceTransformer(self.name, trust_remote_code=False)

    def encode(self, texts: list[str], *, queries: bool = False) -> list[list[float]]:
        # The model card recommends this prefix for short retrieval queries.
        if queries:
            texts = [f"Represent this sentence for searching relevant passages: {text}" for text in texts]
        encoded = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [vector.tolist() for vector in encoded]


def make_embedder(name: str) -> Embedder:
    if name == "hash":
        return HashEmbedder()
    if name == "bge":
        return BgeEmbedder()
    raise ValueError(f"Unknown embedding model: {name}")

