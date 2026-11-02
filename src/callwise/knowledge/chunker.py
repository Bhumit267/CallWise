"""Text chunker that respects paragraph and sentence boundaries with overlap."""

import re
from typing import List


def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences using punctuation boundaries."""
    # Split by period, exclamation, or question mark followed by whitespace
    sentence_endings = re.compile(r"(?<=[.!?])\s+")
    parts = sentence_endings.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def chunk_text(
    text: str,
    target_chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> List[str]:
    """
    Split text into chunks of roughly target_chunk_size characters,
    preserving paragraph and sentence boundaries where possible.
    """
    cleaned = text.strip()
    if not cleaned:
        return []

    if len(cleaned) <= target_chunk_size:
        return [cleaned]

    # Split into paragraphs first
    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]

    # Collect granular units (sentences or paragraph blocks)
    units: List[str] = []
    for para in paragraphs:
        if len(para) <= target_chunk_size:
            units.append(para)
        else:
            sentences = split_into_sentences(para)
            for s in sentences:
                if len(s) > target_chunk_size:
                    # Fallback for very long sentences without punctuation: split on words
                    words = s.split()
                    current_word_chunk = []
                    current_len = 0
                    for w in words:
                        if current_len + len(w) + 1 > target_chunk_size and current_word_chunk:
                            units.append(" ".join(current_word_chunk))
                            current_word_chunk = [w]
                            current_len = len(w)
                        else:
                            current_word_chunk.append(w)
                            current_len += len(w) + 1
                    if current_word_chunk:
                        units.append(" ".join(current_word_chunk))
                else:
                    units.append(s)

    # Accumulate units into chunks with overlap
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_length = 0

    for unit in units:
        unit_len = len(unit)

        if current_length + unit_len + 1 > target_chunk_size and current_chunk:
            # Finalize current chunk
            chunk_str = "\n".join(current_chunk) if any("\n" in u for u in current_chunk) else " ".join(current_chunk)
            chunks.append(chunk_str.strip())

            # Handle overlap: retain trailing units whose combined length is <= chunk_overlap
            overlap_units: List[str] = []
            overlap_length = 0
            for prev_unit in reversed(current_chunk):
                if overlap_length + len(prev_unit) <= chunk_overlap:
                    overlap_units.insert(0, prev_unit)
                    overlap_length += len(prev_unit) + 1
                else:
                    break

            current_chunk = overlap_units + [unit]
            current_length = sum(len(u) + 1 for u in current_chunk)
        else:
            current_chunk.append(unit)
            current_length += unit_len + 1

    if current_chunk:
        chunk_str = "\n".join(current_chunk) if any("\n" in u for u in current_chunk) else " ".join(current_chunk)
        final_chunk = chunk_str.strip()
        if final_chunk and (not chunks or final_chunk != chunks[-1]):
            chunks.append(final_chunk)

    return chunks
