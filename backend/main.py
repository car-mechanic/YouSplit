import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from logging_setup import setup_logging

# Logging VOR allen anderen Projekt-Imports konfigurieren, damit auch deren
# Modul-Logger sofort das einheitliche Format nutzen.
setup_logging()

import models  # noqa: E402,F401 — registriert die Tabellen bei Base.metadata
from database import Base, engine, ensure_schema_updates  # noqa: E402
from routers import lists, members  # noqa: E402

logger = logging.getLogger("yousplit.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Legt fehlende Tabellen beim Start an (Alembic kommt spaeter)
    Base.metadata.create_all(bind=engine)
    # Neue Spalten an bestehenden Tabellen nachruesten (create_all kann das nicht)
    ensure_schema_updates()
    logger.info("Backend gestartet.")
    yield


app = FastAPI(title="YouSplit Backend", lifespan=lifespan)

# Erlaubt dem Vite-Dev-Server (Port 5173), die API aufzurufen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def log_request_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """422er ins Docker-Log schreiben, statt sie lautlos ans Frontend zu geben.

    Diese Fehler wirft FastAPI VOR unserem Endpoint-Code — in den Routern
    kann man sie deshalb nicht abfangen.
    """
    logger.warning(
        "422 Validation Error: %s %s -> %s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    return await request_validation_exception_handler(request, exc)


app.include_router(lists.router, prefix="/api")
app.include_router(members.router, prefix="/api")


# Home-Assistant-Add-on: Das gebaute Frontend wird vom Backend mit ausgeliefert
# (STATIC_DIR, siehe Dockerfile.addon). In der Entwicklung ist es nicht gesetzt.
STATIC_DIR = os.getenv("STATIC_DIR")

if STATIC_DIR and os.path.isdir(STATIC_DIR):
    static_root = os.path.realpath(STATIC_DIR)

    @app.get("/{path:path}", include_in_schema=False)
    def serve_frontend(path: str) -> FileResponse:
        """Liefert Dateien aus dem Build; alles andere ist eine SPA-Route."""
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = os.path.realpath(os.path.join(static_root, path))
        # Pfad darf den Build-Ordner nicht verlassen (../-Angriffe)
        if candidate.startswith(static_root + os.sep) and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(static_root, "index.html"))

else:

    @app.get("/")
    def read_root() -> dict[str, str]:
        return {"status": "YouSplit Backend läuft!"}
