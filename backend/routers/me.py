"""Angemeldeter Home-Assistant-Benutzer, seine Listen und die HA-Benutzerliste.

Alles hier gibt es nur über Ingress (siehe ``ha_identity``). Über den direkten
Port bleibt YouSplit eine App ohne Konto: dort antwortet ``/me`` mit ``null``
und das Frontend nutzt weiter die Merkliste im localStorage.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

import models
import my_lists
import schemas
from database import get_db
from ha_identity import HaUser, current_user, require_user
from ha_users import HaUsersError, fetch_users

router = APIRouter(tags=["me"])


@router.get("/me", response_model=schemas.CurrentUser | None)
def get_me(user: HaUser | None = Depends(current_user)) -> HaUser | None:
    """Der HA-Benutzer dieser Anfrage oder ``null`` (direkter Port, Entwicklung)."""
    return user


@router.get("/me/lists", response_model=list[schemas.MyList])
def get_my_lists(
    user: HaUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> list[schemas.MyList]:
    return my_lists.visible_lists(db, user.id)


@router.put("/me/lists/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def visit_list(
    list_id: uuid.UUID,
    user: HaUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> Response:
    """Merkt die Liste als besucht (beim Öffnen der Liste)."""
    if db.get(models.SharedList, list_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Liste nicht gefunden"
        )
    my_lists.record_visit(db, user.id, list_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/me/lists/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def forget_list(
    list_id: uuid.UUID,
    user: HaUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> Response:
    my_lists.forget(db, user.id, list_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/lists/import", status_code=status.HTTP_204_NO_CONTENT)
def import_lists(
    payload: schemas.BookmarkImport,
    user: HaUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> Response:
    my_lists.import_lists(db, user.id, payload.list_ids)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/ha/users", response_model=list[schemas.HaUserOption])
async def get_ha_users(
    _user: HaUser = Depends(require_user),
) -> list[schemas.HaUserOption]:
    """Auswählbare HA-Benutzer. Nur über Ingress: die Namen sollen nicht über
    den öffentlichen Share-Port abrufbar sein."""
    try:
        users = await fetch_users()
    except HaUsersError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return [schemas.HaUserOption(id=user.id, name=user.name) for user in users]
