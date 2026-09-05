from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


def mount_offline_docs(app: FastAPI) -> None:
    directory = Path(__file__).with_name("static") / "docs"
    app.mount("/docs", StaticFiles(directory=directory, html=True), name="offline-docs")
