from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEMORYOS_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "MemoryOS"
    app_env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8765
    metrics_port: int = 8766
    data_root: Path = Field(default_factory=lambda: Path("var/data"))
    api_keys_json: str = '{"nexus":"dev-nexus-key","morgan":"dev-morgan-key","anya":"dev-anya-key"}'
    default_limit: int = 8
    max_retrieve_limit: int = 20
    interleave_round_limit: int = 2
    default_agent: str = "nexus"

    @property
    def api_keys(self) -> dict[str, str]:
        parsed = json.loads(self.api_keys_json)
        return {str(agent): str(key) for agent, key in parsed.items()}

    @property
    def agents(self) -> list[str]:
        return list(self.api_keys.keys())

    def agent_for_api_key(self, api_key: str) -> str | None:
        for agent, key in self.api_keys.items():
            if key == api_key:
                return agent
        return None
