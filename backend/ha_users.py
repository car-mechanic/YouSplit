"""Benutzerliste von Home Assistant für die Personen-Auswahl.

Die Supervisor-REST-API (``/auth/list``) bräuchte ``hassio_role: admin`` und
liefert keine Benutzer-IDs. Die IDs braucht es aber, weil Ingress den
angemeldeten Benutzer per ID meldet. Deshalb der Websocket-Befehl
``config/auth/list`` von Home Assistant Core über den Supervisor-Proxy
(Add-on-Option ``homeassistant_api: true``).
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

logger = logging.getLogger("yousplit.ha_users")

CORE_WEBSOCKET_URL = "ws://supervisor/core/websocket"
TIMEOUT_SECONDS = 5


class HaUsersError(Exception):
    """Benutzerliste nicht abrufbar (kein Add-on, Core nicht erreichbar …)."""


@dataclass(frozen=True)
class HaUserOption:
    id: str
    name: str


def selectable_users(raw_users: list[dict[str, Any]]) -> list[HaUserOption]:
    """Nur echte, aktive Personen: ohne Systembenutzer wie „Supervisor“ oder
    „Home Assistant Content“. Sortiert nach Anzeigename."""
    options = [
        HaUserOption(
            id=user["id"],
            name=(user.get("name") or user.get("username") or user["id"]).strip(),
        )
        for user in raw_users
        if user.get("is_active") and not user.get("system_generated")
    ]
    return sorted(options, key=lambda option: option.name.casefold())


async def fetch_users() -> list[HaUserOption]:
    """Fragt Home Assistant nach allen Benutzern (wirft ``HaUsersError``)."""
    token = os.getenv("SUPERVISOR_TOKEN")
    if not token:
        raise HaUsersError("Läuft nicht als Home-Assistant-Add-on.")
    try:
        async with asyncio.timeout(TIMEOUT_SECONDS):
            raw_users = await _query_core(token)
    except (OSError, TimeoutError, WebSocketException, ValueError) as exc:
        logger.warning("HA-Benutzerliste nicht abrufbar: %r", exc)
        raise HaUsersError("Home Assistant ist nicht erreichbar.") from exc
    return selectable_users(raw_users)


async def _query_core(token: str) -> list[dict[str, Any]]:
    async with connect(CORE_WEBSOCKET_URL) as websocket:
        # Protokoll: Server meldet auth_required → Token → auth_ok → Befehl
        await websocket.recv()
        await websocket.send(json.dumps({"type": "auth", "access_token": token}))
        auth = json.loads(await websocket.recv())
        if auth.get("type") != "auth_ok":
            raise HaUsersError(
                "Home Assistant lehnt den Zugriff ab (homeassistant_api aktiv?)."
            )
        await websocket.send(json.dumps({"id": 1, "type": "config/auth/list"}))
        reply = json.loads(await websocket.recv())
    if not reply.get("success"):
        raise HaUsersError("Home Assistant liefert keine Benutzerliste.")
    return reply["result"]
