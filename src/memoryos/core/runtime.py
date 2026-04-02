from __future__ import annotations

from memoryos.config import Settings
from memoryos.db.sqlite_store import AgentStore


class MemoryOSRuntime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.stores = {agent: AgentStore(settings, agent) for agent in settings.agents}

    def bootstrap(self) -> None:
        self.settings.data_root.mkdir(parents=True, exist_ok=True)
        for store in self.stores.values():
            store.bootstrap()

    def store_for(self, agent: str) -> AgentStore:
        if agent not in self.stores:
            raise KeyError(f"Unknown agent: {agent}")
        return self.stores[agent]
