"""Angemeldeter Home-Assistant-Benutzer aus den Ingress-Headern.

Über Ingress setzt der Supervisor ``X-Remote-User-Id`` (und Name, Anzeigename)
auf jede Anfrage. Dieselben Header kann aber jeder mitschicken, der Port 8099
direkt erreicht (Share-Links). Deshalb gelten sie nur, wenn die Verbindung vom
Ingress-Proxy des Supervisors kommt. Ohne Ingress gibt es keinen Benutzer, die
App läuft dann wie bisher ohne Konto.
"""

from dataclasses import dataclass

from fastapi import HTTPException, Request, status

# Feste Adresse des Supervisors im Add-on-Netz (hassio, 172.30.32.0/23). Die
# HA-Entwicklerdoku verlangt, Ingress nur von dieser Adresse anzunehmen.
INGRESS_PROXY_IP = "172.30.32.2"

HEADER_USER_ID = "x-remote-user-id"
HEADER_USER_NAME = "x-remote-user-name"
HEADER_DISPLAY_NAME = "x-remote-user-display-name"

# HA-Benutzer-IDs sind 32 Hex-Zeichen; die Grenze schützt nur die Spaltenbreite
MAX_USER_ID_LENGTH = 64


@dataclass(frozen=True)
class HaUser:
    id: str
    name: str
    display_name: str


def _header(request: Request, name: str) -> str:
    """Header als Text. Der Supervisor schickt UTF-8, Starlette dekodiert aber
    Latin-1: ohne Umkodieren würde aus „Jörg“ „JÃ¶rg“."""
    raw = request.headers.get(name, "")
    try:
        raw = raw.encode("latin-1").decode("utf-8")
    except UnicodeError:
        pass
    return raw.strip()


def current_user(request: Request) -> HaUser | None:
    """FastAPI-Dependency: der HA-Benutzer der Anfrage oder ``None``."""
    if request.client is None or request.client.host != INGRESS_PROXY_IP:
        return None
    user_id = _header(request, HEADER_USER_ID)
    if not user_id or len(user_id) > MAX_USER_ID_LENGTH:
        return None
    name = _header(request, HEADER_USER_NAME)
    display_name = _header(request, HEADER_DISPLAY_NAME)
    return HaUser(id=user_id, name=name, display_name=display_name or name or user_id)


def require_user(request: Request) -> HaUser:
    """Wie ``current_user``, aber 401 ohne Ingress-Benutzer."""
    user = current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nur über Home Assistant verfügbar.",
        )
    return user
