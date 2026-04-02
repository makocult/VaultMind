from __future__ import annotations

import math
import re
from hashlib import blake2b


TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
CJK_ONLY_RE = re.compile(r"^[\u4e00-\u9fff]+$")


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for match in TOKEN_RE.finditer(text or ""):
        token = match.group(0).lower()
        if CJK_ONLY_RE.fullmatch(token):
            if token not in tokens:
                tokens.append(token)
            for window in (2, 3):
                if len(token) >= window:
                    for index in range(len(token) - window + 1):
                        piece = token[index : index + window]
                        if piece not in tokens:
                            tokens.append(piece)
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens


def make_summary(text: str, max_len: int = 140) -> str:
    normalized = normalize_text(text)
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 1].rstrip() + "…"


def make_hash_vector(text: str, dims: int = 64) -> list[float]:
    vector = [0.0] * dims
    tokens = tokenize(text)
    if not tokens:
        return vector
    for token in tokens:
        digest = blake2b(token.encode("utf-8"), digest_size=2).digest()
        bucket = int.from_bytes(digest, "big") % dims
        vector[bucket] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def reciprocal_rank_fusion(result_lists: list[list[str]], k: int = 60) -> dict[str, float]:
    fused: dict[str, float] = {}
    for result_list in result_lists:
        for index, item_id in enumerate(result_list, start=1):
            fused[item_id] = fused.get(item_id, 0.0) + 1.0 / (k + index)
    return fused


def extract_query_entities(text: str) -> list[str]:
    tokens = tokenize(text)
    entities: list[str] = []
    for token in tokens:
        if len(token) >= 3 and token not in entities:
            entities.append(token)
    return entities[:5]


def strip_front_matter(markdown_text: str) -> str:
    if markdown_text.startswith("---\n"):
        parts = markdown_text.split("---\n", 2)
        if len(parts) == 3:
            return parts[2].strip()
    return markdown_text.strip()
