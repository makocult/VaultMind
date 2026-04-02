from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from memoryos.api.routes import router
from memoryos.console import register_console
from memoryos.config import Settings
from memoryos.core.runtime import MemoryOSRuntime


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    runtime = MemoryOSRuntime(resolved_settings)
    runtime.bootstrap()

    app = FastAPI(title=resolved_settings.app_name, version="0.1.0")
    app.state.runtime = runtime
    app.include_router(router)
    register_console(app)

    @app.get("/healthz")
    def root_healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def root_readyz() -> dict[str, object]:
        return {
            "status": "ready",
            "agents": runtime.settings.agents,
            "data_root": str(runtime.settings.data_root),
        }

    return app


def main() -> None:
    settings = Settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


app = create_app()


if __name__ == "__main__":
    main()
