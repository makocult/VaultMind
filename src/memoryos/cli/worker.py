from __future__ import annotations

import argparse
import json

from memoryos.config import Settings
from memoryos.core.runtime import MemoryOSRuntime
from memoryos.services.commit import CommitService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MemoryOS commit worker once.")
    parser.add_argument("agent", nargs="?", default=None)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--reindex", action="store_true")
    args = parser.parse_args()

    settings = Settings()
    runtime = MemoryOSRuntime(settings)
    runtime.bootstrap()
    agent = args.agent or settings.default_agent
    store = runtime.store_for(agent)
    result = CommitService().run_once(store, args.limit)
    if args.reindex:
        store.rebuild_indexes()
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
