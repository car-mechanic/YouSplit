"""Liefert das gebaute Frontend aus (nur im Home-Assistant-Add-on).

Über Ingress blendet Home Assistant die App unter
``/api/hassio_ingress/<token>/`` ein und meldet dieses Präfix im Header
``X-Ingress-Path``. Die index.html bekommt deshalb ein passendes
``<base href>``: Assets, API-Aufrufe und Router lösen relativ dazu auf.
Über den direkten Port fehlt der Header, dann bleibt die Basis ``/``.
"""

import html
import os
import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

# Der Header ist auf dem direkt erreichbaren Port frei setzbar. Nur das
# Supervisor-Format zulassen, sonst ließe sich HTML in die Seite einschleusen.
INGRESS_PATH = re.compile(r"^/api/hassio_ingress/[A-Za-z0-9_-]+$")

BASE_TAG = '<base href="/" />'
PUBLIC_URL_META = '<meta name="yousplit-public-url" content="" />'


def render_index(template: str, ingress_path: str | None, public_url: str) -> str:
    """Setzt Basis-Pfad und öffentliche URL (für Share-Links) in die index.html."""
    base = "/"
    if ingress_path and INGRESS_PATH.match(ingress_path):
        base = ingress_path + "/"
    page = template.replace(BASE_TAG, f'<base href="{base}" />')
    return page.replace(
        PUBLIC_URL_META,
        f'<meta name="yousplit-public-url" content="{html.escape(public_url)}" />',
    )


def register_frontend(app: FastAPI, static_dir: str, public_url: str) -> None:
    """Hängt die Catch-all-Route für Build-Dateien und SPA-Routen an."""
    static_root = os.path.realpath(static_dir)
    with open(os.path.join(static_root, "index.html"), encoding="utf-8") as f:
        template = f.read()

    @app.get("/{path:path}", include_in_schema=False, response_model=None)
    def serve_frontend(path: str, request: Request) -> FileResponse | HTMLResponse:
        """Liefert Dateien aus dem Build; alles andere ist eine SPA-Route."""
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = os.path.realpath(os.path.join(static_root, path))
        # Pfad darf den Build-Ordner nicht verlassen (../-Angriffe)
        if (
            candidate.startswith(static_root + os.sep)
            and os.path.isfile(candidate)
            and path != "index.html"
        ):
            return FileResponse(candidate)
        page = render_index(template, request.headers.get("x-ingress-path"), public_url)
        # Basis-Pfad hängt am Header: nicht zwischen Ingress und Port cachen
        return HTMLResponse(page, headers={"Cache-Control": "no-cache"})
