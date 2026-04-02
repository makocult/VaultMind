from __future__ import annotations

from datetime import datetime
from uuid import uuid4


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def new_candidate_id() -> str:
    return f"cand_{_stamp()}_{uuid4().hex[:8]}"


def new_memory_id() -> str:
    return f"mem_{_stamp()}_{uuid4().hex[:8]}"


def new_relation_id() -> str:
    return f"rel_{_stamp()}_{uuid4().hex[:8]}"
