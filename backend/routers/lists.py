import logging
import uuid
from datetime import date, datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    File,
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
from database import get_db
from settlement import calculate_settlement, collect_persons
from splits import fair_split

router = APIRouter(prefix="/lists", tags=["lists"])

logger = logging.getLogger("yousplit.lists")

DUPLICATE_MESSAGE = (
    "Eine Ausgabe mit diesem Betrag am selben Tag existiert bereits."
)


def _utc_today() -> date:
    """Heutiges Datum in UTC — der Vergleichstag der Duplikats-Pruefung, wenn
    kein Ausgabedatum angegeben wurde."""
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
    (unscharf, siehe ``duplicates.shops_match``). Ohne ``title`` (so aktuell bei
    jeder Eingabe) zaehlen nur Betrag und Datum. Der Titel-Vergleich ist fuer
    ein spaeteres Scan-Konzept vorbereitet (siehe AI_CONTEXT.md, 4.7).

    Als Datum eines bestehenden Eintrags gilt sein Ausgabedatum
    (``receipt_date``), falls vorhanden — sonst ersatzweise das Anlagedatum
    (``created_at``). Betraege werden auf Cent gerundet
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


def _duplicate_response() -> JSONResponse:
    """409-Antwort bei erkanntem Duplikat (manuelles Anlegen).

    Das Frontend hat die Werte bereits und fragt den Nutzer, ob er trotzdem
    speichern will.
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


# ---------- Uploads ----------

def _ensure_max_size(data: bytes, max_bytes: int, label: str) -> None:
    """Lehnt zu grosse Uploads mit 413 ab.

    Der Aufrufer liest dafuer hoechstens ``max_bytes + 1`` Bytes: so landet auch
    ein viel zu grosser Upload nie komplett im RAM.
    """
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"{label} ist zu groß (max. {max_bytes // (1024 * 1024)} MB).",
        )


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
    return calculate_settlement(shared_list.expenses, shared_list.members or [])


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
    Ausgabedatum, sonst heute. Bei einer Fremdwaehrung wird der Tageskurs abgerufen
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
    _ensure_max_size(data, MAX_STATEMENT_BYTES, "Das PDF")
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
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
    verteilt (``splits.fair_split``). Betraege sind EUR (Kurs
    1.0). Alles oder nichts: ein einziger Commit am Ende.
    """
    shared_list = _get_list_or_404(db, list_id)

    persons = collect_persons(
        db.query(models.Expense).filter(models.Expense.list_id == list_id).all(),
        shared_list.members or [],
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

