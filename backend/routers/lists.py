import logging
import time
import uuid
from datetime import date, datetime, timezone

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

import bank_statement
import duplicates
import models
import schemas
from currency import ExchangeRateError, get_exchange_rate
import receipt_jobs
from database import SessionLocal, get_db
from ollama_client import (
    ReceiptAnalysisError,
    analyze_receipt,
    ensure_model,
    is_model_available,
)
from settlement import calculate_settlement, collect_persons
from splits import fair_split

router = APIRouter(prefix="/lists", tags=["lists"])

logger = logging.getLogger("yousplit.receipts")

DUPLICATE_MESSAGE = (
    "Eine Ausgabe mit diesem Betrag am selben Tag existiert bereits."
)


def _utc_today() -> date:
    """Heutiges Datum in UTC — der Vergleichstag der Duplikats-Pruefung bei
    manueller Eingabe bzw. wenn der Scan kein Bon-Datum liefert."""
    return datetime.now(timezone.utc).date()


# ---------- Duplikats-Pruefung ----------

def _find_duplicate(
    db: Session,
    list_id: uuid.UUID,
    amount: float,
    on_date: date,
    title: str | None = None,
) -> models.Expense | None:
    """Sucht in der Liste eine Ausgabe mit gleichem Betrag am ``on_date``.

    Wird ``title`` (das Geschaeft) uebergeben, muss auch dieses uebereinstimmen
    (unscharf, siehe ``duplicates.shops_match``) — so beim Bon-Scan. Ohne ``title``
    (manuelle Eingabe) zaehlen nur Betrag und Datum.

    Als Datum eines bestehenden Eintrags gilt sein Bon-Datum (``receipt_date``),
    falls vorhanden — sonst ersatzweise das Anlagedatum (``created_at``). So wird
    beim Scan derselbe Bon auch dann als Duplikat erkannt, wenn er an einem
    anderen Tag noch einmal gescannt wird; bei manueller Eingabe bleibt es beim
    "gleicher Betrag am selben Tag". Betraege werden auf Cent gerundet
    verglichen, damit Fliesskomma-Ungenauigkeiten (24.50 vs. 24.499999) das
    Duplikat nicht verfehlen.
    """
    candidates = (
        db.query(models.Expense)
        .filter(models.Expense.list_id == list_id)
        .all()
    )
    for expense in candidates:
        existing_date = expense.receipt_date or expense.created_at.date()
        if round(expense.amount, 2) != round(amount, 2):
            continue
        if existing_date != on_date:
            continue
        if title is not None and not duplicates.shops_match(expense.title, title):
            continue
        return expense
    return None


def _scan_duplicate_message(
    list_id: uuid.UUID, analysis: schemas.ReceiptAnalysis
) -> str | None:
    """Meldung, falls der gescannte Bon (Geschaeft + Betrag + Datum) schon in der
    Liste ist — sonst ``None``. Eigene DB-Session (laeuft im BackgroundTask).

    Hat der Bon kein lesbares Datum, gilt wie bei der manuellen Eingabe ``heute``
    als Vergleichstag.
    """
    on_date = analysis.receipt_date or _utc_today()
    db = SessionLocal()
    try:
        match = _find_duplicate(
            db, list_id, analysis.amount, on_date, title=analysis.title
        )
        if match is None:
            return None
        amount = f"{match.amount:.2f}".replace(".", ",")
        return (
            f"„{match.title}“ über {amount} {match.currency} vom "
            f"{(match.receipt_date or match.created_at.date()):%d.%m.%Y} ist "
            "bereits in der Liste. Es wurde nichts hinzugefügt."
        )
    finally:
        db.close()


def _duplicate_response() -> JSONResponse:
    """409-Antwort bei erkanntem Duplikat (nur noch manueller Pfad).

    Der Bon-Scan laeuft seit Roadmap 4.0 #2 asynchron (Fire & Forget) und liefert
    sofort 202 — dort laeuft die Duplikats-Pruefung im Hintergrund und meldet sich
    ueber den Status ``duplicate`` des ReceiptJob. Beim manuellen Anlegen bleibt
    die 409-Warnung; das Frontend hat die Werte bereits.
    """
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT, content={"detail": DUPLICATE_MESSAGE}
    )


def _get_list_or_404(db: Session, list_id: uuid.UUID) -> models.SharedList:
    shared_list = db.get(models.SharedList, list_id)
    if shared_list is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Liste nicht gefunden"
        )
    return shared_list


def _get_expense_or_404(
    db: Session, list_id: uuid.UUID, expense_id: uuid.UUID
) -> models.Expense:
    """Laedt eine Ausgabe und stellt sicher, dass sie zur Liste gehoert (sonst 404)."""
    expense = db.get(models.Expense, expense_id)
    if expense is None or expense.list_id != list_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ausgabe nicht gefunden"
        )
    return expense


# ---------- Kassenbon-Scan (OCR) ----------

def _ensure_image(receipt: UploadFile) -> None:
    """Stellt sicher, dass der Upload ueberhaupt ein Bild ist (sonst 400).

    Guard Clause VOR der teuren KI-Analyse — spart eine sinnlose Ollama-Anfrage,
    wenn versehentlich z. B. ein PDF hochgeladen wurde.
    """
    if receipt.content_type is None or not receipt.content_type.startswith(
        "image/"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bitte ein Bild hochladen (JPEG, PNG, ...).",
        )


async def _process_receipt_in_background(
    job_id: uuid.UUID, list_id: uuid.UUID, payer_name: str, image_bytes: bytes
) -> None:
    """Hintergrund-Verarbeitung eines Bons (Roadmap 4.0 #2, "Fire & Forget").

    Laeuft NACH der bereits gesendeten 202-Antwort, also ausserhalb des
    Request-Lebenszyklus. Deshalb:
    - **eigene DB-Session** (``SessionLocal``) — die Request-Session aus
      ``get_db`` ist zu diesem Zeitpunkt schon geschlossen.
    - **kein HTTP-Fehler moeglich**: Ausfaelle werden geloggt UND im
      ``ReceiptJob`` (Status ``failed`` + Ursache) festgehalten — das Frontend
      fragt den Status ab und zeigt ihn an (Bugfix 2026-09-25).

    Fairer Split: der extrahierte Betrag wird gleichmaessig auf ALLE aktuell in
    der Liste bekannten Personen plus den Zahler verteilt (``splits``-JSON).
    """
    started = time.monotonic()
    logger.info(
        "Job %s: Start (Liste %s, Zahler '%s', %d KB)",
        job_id,
        list_id,
        payer_name,
        len(image_bytes) // 1024,
    )
    try:
        # Fehlt das Modell (z. B. nach Volume-Reset), dem Nutzer den langen
        # Download ansagen, statt nur "wird verarbeitet" zu zeigen.
        if not await is_model_available():
            receipt_jobs.set_detail(
                job_id,
                "KI-Modell wird einmalig heruntergeladen (~3 GB) – das kann "
                "einige Minuten dauern …",
            )
            await ensure_model()
            receipt_jobs.set_detail(job_id, None)

        receipt_jobs.set_progress(job_id, receipt_jobs.PROGRESS_ANALYZING)
        analysis_started = time.monotonic()
        analysis = await analyze_receipt(image_bytes)
        receipt_jobs.record_analysis_duration(time.monotonic() - analysis_started)
        receipt_jobs.set_progress(job_id, receipt_jobs.PROGRESS_ANALYZED)
        logger.info(
            "Job %s: erkannt '%s' %.2f %s, Kategorie %s, Datum %s",
            job_id,
            analysis.title,
            analysis.amount,
            analysis.currency,
            analysis.category,
            analysis.receipt_date,
        )
        # Duplikats-Pruefung (Geschaeft + Betrag + Datum) VOR dem Kursabruf und
        # dem Insert: nichts anlegen, sondern den Nutzer entscheiden lassen.
        duplicate_message = _scan_duplicate_message(list_id, analysis)
        if duplicate_message is not None:
            logger.info("Job %s: Duplikat erkannt – %s", job_id, duplicate_message)
            receipt_jobs.mark_duplicate(
                job_id, duplicate_message, analysis.model_dump(mode="json")
            )
            return
        receipt_jobs.set_progress(job_id, receipt_jobs.PROGRESS_CHECKED)
        rate = await get_exchange_rate(analysis.currency)
        receipt_jobs.set_progress(job_id, receipt_jobs.PROGRESS_SAVING)
        expense_id = _insert_scanned_expense(list_id, payer_name, analysis, rate)
    except ReceiptAnalysisError as exc:
        logger.error("Job %s: KI-Analyse fehlgeschlagen: %s", job_id, exc)
        receipt_jobs.mark_failed(job_id, str(exc))
        return
    except ExchangeRateError as exc:
        logger.error("Job %s: Wechselkurs fehlgeschlagen: %s", job_id, exc)
        receipt_jobs.mark_failed(job_id, str(exc))
        return
    except Exception as exc:  # noqa: BLE001 — im Hintergrund darf nichts hochblubbern
        logger.exception("Job %s: unerwarteter Fehler", job_id)
        receipt_jobs.mark_failed(
            job_id, f"Unerwarteter Fehler beim Verarbeiten ({type(exc).__name__})"
        )
        return

    receipt_jobs.mark_done(job_id, expense_id)
    logger.info(
        "Job %s: fertig nach %.1f s → Ausgabe %s",
        job_id,
        time.monotonic() - started,
        expense_id,
    )


def _insert_scanned_expense(
    list_id: uuid.UUID,
    payer_name: str,
    analysis: schemas.ReceiptAnalysis,
    rate: float,
) -> uuid.UUID:
    """Legt die gescannte Ausgabe mit fairem Split an (eigene DB-Session).

    Fehler werden NICHT hier abgefangen, sondern an den Aufrufer weitergereicht,
    damit der Job sauber auf ``failed`` gesetzt wird.
    """
    db = SessionLocal()
    try:
        # Alle bekannten Personen der Liste + den Zahler des Bons als Teilnehmer.
        existing = (
            db.query(models.Expense)
            .filter(models.Expense.list_id == list_id)
            .all()
        )
        persons = collect_persons(existing)
        if payer_name not in persons:
            persons.append(payer_name)

        splits = fair_split(analysis.amount, persons)
        # split_ratio kohaerent halten (Eigenanteil des Zahlers als Fallback).
        payer_share = splits.get(payer_name, 0.0)
        split_ratio = payer_share / analysis.amount if analysis.amount > 0 else 0.5

        expense = models.Expense(
            list_id=list_id,
            title=analysis.title,
            amount=analysis.amount,
            payer_name=payer_name,
            split_ratio=split_ratio,
            category=analysis.category,
            receipt_date=analysis.receipt_date,
            currency=analysis.currency,
            exchange_rate=rate,
            splits=splits,
        )
        db.add(expense)
        db.commit()
        return expense.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------- Wechselkurs (Multi-Currency) ----------

async def _rate_or_502(currency: str) -> float:
    """Ermittelt den Tageskurs (EUR je Einheit ``currency``) und uebersetzt einen
    Ausfall der Kurs-API in HTTP 502.

    Bewusst kein stiller Fallback auf 1.0: ein falscher Kurs wuerde die
    EUR-Salden verfaelschen. Fuer EUR liefert ``get_exchange_rate`` ohne API-Aufruf
    direkt 1.0.
    """
    try:
        return await get_exchange_rate(currency)
    except ExchangeRateError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc


# ---------- Listen ----------

@router.post(
    "",
    response_model=schemas.SharedListResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_list(
    payload: schemas.SharedListCreate,
    db: Session = Depends(get_db),
) -> models.SharedList:
    """Legt eine neue geteilte Liste an. Ihre UUID dient als Share-Link."""
    new_list = models.SharedList(title=payload.title)
    db.add(new_list)
    db.commit()
    db.refresh(new_list)
    return new_list


@router.get("/{list_id}", response_model=schemas.SharedListResponse)
def get_list(
    list_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> models.SharedList:
    """Laedt eine Liste inklusive aller Ausgaben (404, wenn UUID unbekannt)."""
    return _get_list_or_404(db, list_id)


@router.get("/{list_id}/settlement", response_model=schemas.SettlementResponse)
def get_settlement(
    list_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> schemas.SettlementResponse:
    """Kassensturz fuer N Personen: wer schuldet wem wie viel (minimal)."""
    shared_list = _get_list_or_404(db, list_id)
    return calculate_settlement(shared_list.expenses)


# ---------- Ausgaben ----------

@router.post(
    "/{list_id}/expenses",
    response_model=schemas.ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_expense(
    list_id: uuid.UUID,
    payload: schemas.ExpenseCreate,
    force: bool = Query(
        default=False,
        description="Duplikats-Warnung uebergehen und trotzdem speichern",
    ),
    db: Session = Depends(get_db),
) -> models.Expense | JSONResponse:
    """Legt eine Ausgabe manuell an.

    Prueft vorher auf ein Duplikat (gleicher Betrag am selben Tag) und antwortet
    dann mit 409 — ausser ``force=true``. Vergleichstag ist das mitgeschickte
    Bon-Datum, sonst heute. Bei einer Fremdwaehrung wird der Tageskurs abgerufen
    und mitgespeichert (EUR-Betrag = amount * exchange_rate).
    """
    _get_list_or_404(db, list_id)

    on_date = payload.receipt_date or _utc_today()
    if not force and _find_duplicate(db, list_id, payload.amount, on_date) is not None:
        return _duplicate_response()

    # Kurs erst NACH der Duplikats-Pruefung holen — spart bei einem Duplikat den
    # (fuer EUR ohnehin entfallenden) API-Aufruf.
    rate = await _rate_or_502(payload.currency)

    expense = models.Expense(
        list_id=list_id, exchange_rate=rate, **payload.model_dump()
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.put(
    "/{list_id}/expenses/{expense_id}",
    response_model=schemas.ExpenseResponse,
)
async def update_expense(
    list_id: uuid.UUID,
    expense_id: uuid.UUID,
    payload: schemas.ExpenseUpdate,
    db: Session = Depends(get_db),
) -> models.Expense:
    """Aktualisiert eine Ausgabe vollstaendig (PUT, inkl. Datum & Waehrung)."""
    expense = _get_expense_or_404(db, list_id, expense_id)

    # Kurs nur dann neu abrufen, wenn sich die Waehrung geaendert hat — sonst
    # bleibt der gespeicherte Kurs erhalten (unnoetigen API-Aufruf vermeiden).
    if payload.currency != expense.currency:
        expense.exchange_rate = await _rate_or_502(payload.currency)

    # Vollstaendige Aktualisierung der bearbeitbaren Felder. Die Duplikats-
    # Pruefung greift bewusst NUR beim Neuanlegen, nicht beim Bearbeiten.
    expense.title = payload.title
    expense.amount = payload.amount
    expense.payer_name = payload.payer_name
    expense.split_ratio = payload.split_ratio
    expense.category = payload.category
    expense.receipt_date = payload.receipt_date
    expense.currency = payload.currency
    # Advanced Split: explizite Pro-Person-Aufteilung uebernehmen (oder loeschen)
    expense.splits = payload.splits

    db.commit()
    db.refresh(expense)
    return expense


@router.delete(
    "/{list_id}/expenses/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_expense(
    list_id: uuid.UUID,
    expense_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    """Loescht eine Ausgabe (204 ohne Body)."""
    expense = _get_expense_or_404(db, list_id, expense_id)
    db.delete(expense)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{list_id}/receipts",
    response_model=schemas.ReceiptUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_receipt(
    list_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    payer_name: str = Form(min_length=1, max_length=100),
    receipt: UploadFile = File(),
    db: Session = Depends(get_db),
) -> schemas.ReceiptUploadResponse:
    """Bon-Upload — "Fire & Forget" (Roadmap 4.0 #2) mit Status-Job.

    Validiert nur Liste + Bildtyp, liest das Bild in den RAM, legt einen
    ``ReceiptJob`` (Status ``processing``) an und stoesst die teure KI-Analyse
    **plus** den DB-Insert als BackgroundTask an. Antwortet **sofort** mit HTTP
    202 und der ``job_id``. Den Fortschritt fragt das Frontend ueber
    ``GET /lists/{id}/receipt-jobs`` ab (Bugfix 2026-09-25 — vorher scheiterten
    Scans still).

    Die Duplikats-Pruefung (Geschaeft + Betrag + Datum) passiert im Hintergrund:
    ein bereits vorhandener Bon wird nicht angelegt, der Job bekommt stattdessen
    den Status ``duplicate`` (Bestaetigung ueber ``…/receipt-jobs/{id}/confirm``).
    """
    _get_list_or_404(db, list_id)
    _ensure_image(receipt)

    # Bild im RAM festhalten: die UploadFile ist nach der Antwort nicht mehr
    # lesbar, der BackgroundTask laeuft aber erst danach.
    image_bytes = await receipt.read()

    job = models.ReceiptJob(
        list_id=list_id,
        payer_name=payer_name,
        filename=receipt.filename[:255] if receipt.filename else None,
        status=receipt_jobs.STATUS_PROCESSING,
        progress=receipt_jobs.PROGRESS_ACCEPTED,
    )
    db.add(job)
    db.commit()
    logger.info(
        "Job %s: Bon '%s' angenommen (Liste %s)", job.id, receipt.filename, list_id
    )

    background_tasks.add_task(
        _process_receipt_in_background, job.id, list_id, payer_name, image_bytes
    )
    return schemas.ReceiptUploadResponse(
        status=receipt_jobs.STATUS_PROCESSING, job_id=job.id
    )


@router.get(
    "/{list_id}/receipt-jobs",
    response_model=list[schemas.ReceiptJobResponse],
)
def list_receipt_jobs(
    list_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[schemas.ReceiptJobResponse]:
    """Alle noch nicht quittierten Bon-Scans der Liste (neueste zuerst).

    Das Frontend pollt diesen Endpunkt, solange ein Job ``processing`` ist.
    ``done``-Jobs quittiert es nach dem Neuladen der Liste per DELETE,
    ``failed``-Jobs, sobald der Nutzer die Fehlermeldung verwirft.
    """
    _get_list_or_404(db, list_id)
    jobs = (
        db.query(models.ReceiptJob)
        .filter(models.ReceiptJob.list_id == list_id)
        .order_by(models.ReceiptJob.created_at.desc())
        .all()
    )
    # Erwartete Analyse-Dauer fuer die Fortschrittsanzeige an jeden Job haengen
    estimate = receipt_jobs.expected_analysis_seconds()
    return [
        schemas.ReceiptJobResponse.model_validate(job).model_copy(
            update={"estimated_seconds": estimate}
        )
        for job in jobs
    ]


@router.post(
    "/{list_id}/receipt-jobs/{job_id}/confirm",
    response_model=schemas.ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_duplicate_receipt(
    list_id: uuid.UUID,
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> models.Expense:
    """"Trotzdem hinzufuegen": legt den Bon eines ``duplicate``-Jobs doch an.

    Nutzt die beim Scan gespeicherten Bon-Daten (keine erneute KI-Analyse) und
    quittiert den Job. 404, wenn der Job unbekannt ist; 409, wenn er kein
    wartendes Duplikat (mehr) ist.
    """
    job = db.get(models.ReceiptJob, job_id)
    if job is None or job.list_id != list_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Scan nicht gefunden"
        )
    if job.status != receipt_jobs.STATUS_DUPLICATE or not job.result:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dieser Scan wartet auf keine Bestaetigung.",
        )

    analysis = schemas.ReceiptAnalysis.model_validate(job.result)
    rate = await _rate_or_502(analysis.currency)
    expense_id = _insert_scanned_expense(list_id, job.payer_name, analysis, rate)

    db.delete(job)
    db.commit()
    expense = db.get(models.Expense, expense_id)
    assert expense is not None  # gerade angelegt
    return expense


@router.delete(
    "/{list_id}/receipt-jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def dismiss_receipt_job(
    list_id: uuid.UUID,
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    """Quittiert (loescht) einen Job. Idempotent: unbekannte Jobs → trotzdem 204."""
    job = db.get(models.ReceiptJob, job_id)
    if job is not None and job.list_id == list_id:
        db.delete(job)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Kontoauszug-Import (Epic 4.0 #3) ----------

# Grosszuegig (mehrseitige Jahresauszuege), aber begrenzt.
MAX_STATEMENT_BYTES = 15 * 1024 * 1024


@router.post(
    "/{list_id}/bank-statement/parse",
    response_model=schemas.BankStatementPreview,
)
def parse_bank_statement(
    list_id: uuid.UUID,
    statement: UploadFile = File(),
    db: Session = Depends(get_db),
) -> schemas.BankStatementPreview:
    """Liest einen Kontoauszug (PDF) und liefert die erkannten Buchungen als
    **Vorschau** — es wird nichts gespeichert und das PDF nicht aufbewahrt.

    Bewusst ``def`` (nicht ``async``): das PDF-Parsen ist CPU-gebunden und laeuft
    so im Threadpool, ohne den Event-Loop zu blockieren. Lebensmittel werden ueber
    die gelernten ``CategoryRule``-Stichwoerter der Liste (Vorrang) und die
    eingebaute Haendlerliste erkannt. Bereits vorhandene Ausgaben (gleicher Betrag
    am selben Tag) werden als ``duplicate`` markiert, damit ein erneuter Import
    desselben Auszugs nichts doppelt anlegt.
    """
    _get_list_or_404(db, list_id)

    data = statement.file.read(MAX_STATEMENT_BYTES + 1)
    if len(data) > MAX_STATEMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Das PDF ist zu groß (max. 15 MB).",
        )
    # Magic Number statt nur Content-Type: Browser/Mobilgeraete setzen den Typ
    # nicht immer zuverlaessig.
    if not data.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bitte eine PDF-Datei hochladen.",
        )

    try:
        result = bank_statement.parse_statement(data)
    except bank_statement.StatementParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    rules = [
        (rule.recipient_keyword, rule.category)
        for rule in db.query(models.CategoryRule)
        .filter(models.CategoryRule.list_id == list_id)
        .all()
    ]
    existing_keys = {
        (round(expense.amount, 2), expense.receipt_date or expense.created_at.date())
        for expense in db.query(models.Expense)
        .filter(models.Expense.list_id == list_id)
        .all()
    }

    transactions: list[schemas.BankTransaction] = []
    for index, booking in enumerate(result.bookings):
        classification = bank_statement.classify(booking.description, rules)
        is_expense = booking.amount < 0
        transactions.append(
            schemas.BankTransaction(
                index=index,
                booking_date=booking.booking_date,
                description=booking.description,
                amount=booking.amount,
                category=classification.category,
                label=classification.label,
                # Einnahmen (Erstattungen, Gehalt) sind nie "Lebensmittelkosten"
                is_food=classification.is_food and is_expense,
                duplicate=is_expense
                and booking.booking_date is not None
                and (round(abs(booking.amount), 2), booking.booking_date)
                in existing_keys,
                sign_guessed=booking.sign_guessed,
            )
        )

    logger.info(
        "Kontoauszug gelesen (Liste %s): %d Buchungen, %d Lebensmittel",
        list_id,
        len(transactions),
        sum(1 for t in transactions if t.is_food),
    )
    return schemas.BankStatementPreview(
        transactions=transactions, warnings=result.warnings
    )


@router.post(
    "/{list_id}/bank-statement/import",
    response_model=schemas.BankImportResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_bank_statement(
    list_id: uuid.UUID,
    payload: schemas.BankImportRequest,
    db: Session = Depends(get_db),
) -> schemas.BankImportResponse:
    """Legt die in der Vorschau bestaetigten Buchungen als **einzelne Ausgaben** an.

    Jede Buchung wird fair auf alle bekannten Personen der Liste plus den Zahler
    verteilt (``splits.fair_split``, wie beim Bon-Scan). Betraege sind EUR (Kurs
    1.0). Alles oder nichts: ein einziger Commit am Ende.
    """
    _get_list_or_404(db, list_id)

    persons = collect_persons(
        db.query(models.Expense).filter(models.Expense.list_id == list_id).all()
    )
    if payload.payer_name not in persons:
        persons.append(payload.payer_name)

    total = 0.0
    for item in payload.items:
        splits = fair_split(item.amount, persons)
        payer_share = splits.get(payload.payer_name, 0.0)
        db.add(
            models.Expense(
                list_id=list_id,
                title=item.title,
                amount=item.amount,
                payer_name=payload.payer_name,
                split_ratio=payer_share / item.amount,
                category=payload.category,
                receipt_date=item.booking_date,
                currency="EUR",
                exchange_rate=1.0,
                splits=splits,
            )
        )
        total += item.amount
    db.commit()

    logger.info(
        "Kontoauszug-Import (Liste %s): %d Ausgaben, %.2f EUR, Zahler '%s'",
        list_id,
        len(payload.items),
        total,
        payload.payer_name,
    )
    return schemas.BankImportResponse(
        created=len(payload.items), total=round(total, 2)
    )

