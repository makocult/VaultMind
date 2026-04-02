from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


UI_DIR = Path(__file__).resolve().parent / "ui"
ASSETS_DIR = UI_DIR / "assets"


def register_console(app: FastAPI) -> None:
    app.mount("/console/assets", StaticFiles(directory=ASSETS_DIR), name="console-assets")

    @app.get("/console", include_in_schema=False)
    def console_index() -> FileResponse:
        return FileResponse(UI_DIR / "index.html")
