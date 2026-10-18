"""„Meine Listen“ eines Home-Assistant-Benutzers (2026-10-18).

Sichtbar sind Listen, die der Benutzer geöffnet hat (``ListBookmark``), und
Listen, in denen er als Person verknüpft ist (``SharedList.member_users``).
Beides liegt auf dem Server, deshalb sieht er auf jedem Gerät dieselben Listen.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

import models
import schemas


def visible_lists(db: Session, user_id: str) -> list[schemas.MyList]:
    """Alle Listen des Benutzers, zuletzt besuchte zuerst."""
    visits = {
        bookmark.list_id: bookmark.last_visit
        for bookmark in db.scalars(
            select(models.ListBookmark).where(models.ListBookmark.user_id == user_id)
        )
    }
    rows = db.execute(
        select(
            models.SharedList.id,
            models.SharedList.title,
            models.SharedList.created_at,
            models.SharedList.member_users,
        )
    )
    # Haushaltsgroesse (wenige Dutzend Listen): Filtern in Python statt
    # JSON-Abfrage, die zwischen PostgreSQL und SQLite (Tests) abweicht.
    found: list[tuple[datetime, schemas.MyList]] = []
    for list_id, title, created_at, member_users in rows:
        is_member = user_id in (member_users or {}).values()
        last_visit = visits.get(list_id)
        if last_visit is None and not is_member:
            continue
        found.append(
            (
                last_visit or created_at,
                schemas.MyList(
                    id=list_id, title=title, last_visit=last_visit, is_member=is_member
                ),
            )
        )
    found.sort(key=lambda entry: entry[0], reverse=True)
    return [entry for _, entry in found]


def record_visit(db: Session, user_id: str, list_id: uuid.UUID) -> None:
    """Merkt die Liste mit Zeitstempel jetzt vor (legt den Eintrag ggf. an)."""
    now = datetime.now(timezone.utc)
    bookmark = db.get(models.ListBookmark, (user_id, list_id))
    if bookmark is None:
        db.add(models.ListBookmark(user_id=user_id, list_id=list_id, last_visit=now))
    else:
        bookmark.last_visit = now
    db.commit()


def forget(db: Session, user_id: str, list_id: uuid.UUID) -> None:
    """Nimmt die Liste aus „Meine Listen“ (die Liste selbst bleibt bestehen)."""
    bookmark = db.get(models.ListBookmark, (user_id, list_id))
    if bookmark is not None:
        db.delete(bookmark)
        db.commit()


def import_lists(db: Session, user_id: str, list_ids: list[uuid.UUID]) -> None:
    """Übernimmt die lokal gemerkten Listen eines Geräts.

    Unbekannte IDs (gelöschte Listen, Tippfehler) fallen still heraus.
    Bestehende Einträge behalten ihren Zeitstempel: das Gerät meldet seine
    Merkliste bei jedem Aufruf der Startseite erneut.
    """
    wanted = set(list_ids)
    if not wanted:
        return
    existing = set(
        db.scalars(
            select(models.SharedList.id).where(models.SharedList.id.in_(wanted))
        )
    )
    known = set(
        db.scalars(
            select(models.ListBookmark.list_id).where(
                models.ListBookmark.user_id == user_id
            )
        )
    )
    now = datetime.now(timezone.utc)
    for list_id in existing - known:
        db.add(models.ListBookmark(user_id=user_id, list_id=list_id, last_visit=now))
    db.commit()
