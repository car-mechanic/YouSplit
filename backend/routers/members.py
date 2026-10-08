"""Personen einer Liste (2026-10-08).

Eigenes Modul statt Anbau an ``routers/lists.py`` (das ist schon gross, siehe
AI_CONTEXT.md 3.5). Die Personen legt das Tutorial einer neuen Liste fest; sie
lassen sich spaeter ueber den Kopf der Liste aendern.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db

router = APIRouter(prefix="/lists", tags=["members"])


@router.put("/{list_id}/members", response_model=schemas.SharedListResponse)
def set_members(
    list_id: uuid.UUID,
    payload: schemas.MembersUpdate,
    db: Session = Depends(get_db),
) -> models.SharedList:
    """Ersetzt die Personen der Liste (Namen getrimmt, ohne Doppelte).

    Bestehende Ausgaben bleiben unberuehrt: wer aus der Liste entfernt wird, aber
    in Ausgaben vorkommt, zaehlt im Kassensturz weiter mit.
    """
    shared_list = db.get(models.SharedList, list_id)
    if shared_list is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Liste nicht gefunden"
        )
    shared_list.members = payload.members
    db.commit()
    db.refresh(shared_list)
    return shared_list
