"""Status-Verwaltung der asynchronen Bon-Scans (Receipt-Jobs, Bugfix 2026-09-25).

Kapselt alle Zustandswechsel eines ``ReceiptJob`` an einer Stelle. Die Funktionen
oeffnen jeweils eine **eigene, kurze DB-Session** (``SessionLocal``), weil sie
aus dem BackgroundTask bzw. dem ``lifespan`` heraus laufen — dort gibt es keine
Request-Session aus ``get_db``.
"""

import logging
import uuid

import models
from database import SessionLocal

logger = logging.getLogger("yousplit.receipts")

STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_FAILED = "failed"

ORPHANED_MESSAGE = (
    "Die Verarbeitung wurde durch einen Neustart des Servers abgebrochen. "
    "Bitte den Bon erneut scannen."
)


def set_detail(job_id: uuid.UUID, detail: str | None) -> None:
    """Setzt einen Fortschritts-Hinweis fuer einen laufenden Job."""
    _update(job_id, detail=detail)


def mark_done(job_id: uuid.UUID, expense_id: uuid.UUID) -> None:
    """Job erfolgreich: verknuepft die angelegte Ausgabe."""
    _update(job_id, status=STATUS_DONE, detail=None, expense_id=expense_id)


def mark_failed(job_id: uuid.UUID, error: str) -> None:
    """Job gescheitert: speichert die (nutzerverstaendliche) Ursache."""
    _update(job_id, status=STATUS_FAILED, detail=None, error=error[:500])


def _update(job_id: uuid.UUID, **fields: object) -> None:
    """Schreibt Felder eines Jobs. Fehler hier duerfen den Task nicht abbrechen."""
    db = SessionLocal()
    try:
        job = db.get(models.ReceiptJob, job_id)
        if job is None:
            # Liste geloescht oder Job schon quittiert — nichts zu tun
            logger.info("Job %s existiert nicht mehr, Update verworfen", job_id)
            return
        for key, value in fields.items():
            setattr(job, key, value)
        db.commit()
    except Exception:  # noqa: BLE001 — Status-Update ist "best effort"
        db.rollback()
        logger.exception("Status-Update fuer Job %s fehlgeschlagen", job_id)
    finally:
        db.close()


def fail_orphaned_jobs() -> None:
    """Beim Start: noch "laufende" Jobs als fehlgeschlagen markieren.

    Ein BackgroundTask lebt nur im Speicher des Backend-Prozesses. Nach einem
    Neustart (oder ``uvicorn --reload`` bei Code-Aenderungen) kann ein Job mit
    Status ``processing`` nie mehr fertig werden — ohne diesen Schritt wuerde
    das Frontend endlos "wird verarbeitet" anzeigen.
    """
    db = SessionLocal()
    try:
        orphaned = (
            db.query(models.ReceiptJob)
            .filter(models.ReceiptJob.status == STATUS_PROCESSING)
            .all()
        )
        for job in orphaned:
            job.status = STATUS_FAILED
            job.detail = None
            job.error = ORPHANED_MESSAGE
        db.commit()
        if orphaned:
            logger.warning(
                "%d abgebrochene(n) Bon-Scan(s) nach Neustart als fehlgeschlagen markiert",
                len(orphaned),
            )
    except Exception:  # noqa: BLE001 — darf den Start nicht verhindern
        db.rollback()
        logger.exception("Aufraeumen verwaister Bon-Scans fehlgeschlagen")
    finally:
        db.close()
