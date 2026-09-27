"""Small, inspectable chunking baselines for teaching source boundaries."""

from __future__ import annotations

import re


def fixed_character_chunks(text: str, maximum_length: int) -> list[str]:
    """Split text at a fixed width, even when a sentence crosses the boundary."""
    if maximum_length < 1:
        raise ValueError("Maximum length must be positive")
    return [text[position:position + maximum_length]
            for position in range(0, len(text), maximum_length)]


def paragraph_chunks(text: str, maximum_length: int) -> list[str]:
    """Pack whole paragraphs without silently splitting an oversized paragraph."""
    if maximum_length < 1:
        raise ValueError("Maximum length must be positive")
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text.strip())
                  if paragraph.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > maximum_length:
            raise ValueError("A paragraph exceeds the maximum length; review its boundary")
        combined = f"{current}\n\n{paragraph}" if current else paragraph
        if len(combined) <= maximum_length:
            current = combined
        else:
            chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks
