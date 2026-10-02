import uuid
from datetime import date, datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from currency import SUPPORTED_CURRENCIES

# Toleranz beim Abgleich "Summe der splits == amount" (Advanced Split). Pro
# Teilnehmer kann durch die 1-Cent-Rundung minimal etwas abweichen; wir erlauben
# einen Cent je Person plus einen Sockel, damit valide Aufteilungen nie an
# Fliesskomma-Rauschen scheitern, grobe Fehler (falsche Summe) aber auffallen.
_SPLIT_SUM_TOLERANCE_BASE = 0.01


def _validate_splits(value: object) -> dict[str, float] | None:
    """Prueft die Pro-Person-Aufteilung: Objekt {Name: Betrag} mit Betraegen >= 0.

    Reine Feld-Validierung (ohne Bezug zu ``amount`` — der Summen-Abgleich passiert
    im ``model_validator``). ``None``/leeres Objekt bedeutet "keine feine
    Aufteilung" und wird zu ``None`` normalisiert (Fallback auf ``split_ratio``).
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("splits muss ein Objekt {Name: Betrag} sein")
    if not value:
        return None
    result: dict[str, float] = {}
    for name, share in value.items():
        key = str(name).strip()
        if not key:
            raise ValueError("splits enthaelt einen leeren Namen")
        amount = float(share)
        if amount < 0:
            raise ValueError(f"splits-Betrag fuer '{key}' darf nicht negativ sein")
        result[key] = amount
    return result


def _ensure_splits_match_amount(
    splits: dict[str, float] | None, amount: float
) -> None:
    """Stellt sicher, dass die Summe der ``splits`` (grob) dem ``amount`` entspricht.

    Wird als Model-Validator nach dem Parsen genutzt (braucht ``amount``). Eine
    tolerante Pruefung, weil das Frontend die Betraege auf Cent rundet: erlaubt
    ist ein Cent je Person plus ein Sockel. Grobe Fehler (Summe passt nicht zum
    Gesamtbetrag) fuehren zu HTTP 422, statt still einen falschen Kassensturz zu
    erzeugen.
    """
    if not splits:
        return
    total = sum(splits.values())
    tolerance = _SPLIT_SUM_TOLERANCE_BASE * (len(splits) + 1)
    if abs(total - amount) > tolerance:
        raise ValueError(
            f"Summe der Aufteilung ({total:.2f}) weicht vom Betrag "
            f"({amount:.2f}) ab"
        )


def _normalize_currency(value: object) -> str:
    """Währungscode auf Großschreibung normalisieren und gegen die unterstützte
    Liste prüfen. Ungültige Eingaben werden abgelehnt (→ HTTP 422), damit keine
    Ausgabe mit einer Währung landet, für die es keinen Kurs gibt."""
    code = str(value).strip().upper()
    if code not in SUPPORTED_CURRENCIES:
        raise ValueError(
            f"Währung '{code}' nicht unterstützt (erlaubt: "
            f"{', '.join(SUPPORTED_CURRENCIES)})"
        )
    return code


def _parse_flexible_date(value: object) -> date | None:
    """Wandelt gaengige Datumsformate in ein ``date`` — oder ``None``.

    Genutzt fuer das von der Vision-KI gelesene Bon-Datum: Modelle liefern es
    trotz Prompt mal als ISO ("2026-07-18"), mal deutsch ("18.07.2026") und
    gelegentlich mit angehaengter Uhrzeit. Ist der Wert unlesbar, geben wir
    bewusst ``None`` zurueck, statt den ganzen Scan an einem fehlenden Datum
    scheitern zu lassen.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None

    raw = value.strip()
    if not raw:
        return None
    # Eine evtl. angehaengte Uhrzeit abschneiden ("2026-07-18 14:30" / "...T...")
    raw = raw.replace("T", " ").split(" ", 1)[0]
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


# ---------- Expenses ----------

class ExpenseCreate(BaseModel):
    """Request-Body zum Anlegen einer Ausgabe (manuell oder erzwungener Scan)."""

    title: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0)
    payer_name: str = Field(min_length=1, max_length=100)
    split_ratio: float = Field(default=0.5, ge=0.0, le=1.0)
    category: str = "Unknown/Manuell"
    # Bon-Datum vom Scan: erlaubt der Duplikats-Pruefung, denselben Bon auch an
    # einem anderen Tag zu erkennen. Bei rein manueller Eingabe ``None``.
    receipt_date: date | None = None
    # Erfassungswaehrung (Roadmap 2.0 #3). Der Kurs (exchange_rate) wird NICHT vom
    # Client geschickt, sondern serverseitig tagesaktuell ermittelt.
    currency: str = "EUR"
    # Advanced Split (Roadmap 3.0 #3): explizite Pro-Person-Aufteilung
    # {Name: Betrag} in der Erfassungswaehrung. None → Fallback split_ratio.
    splits: dict[str, float] | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: object) -> str:
        return _normalize_currency(value)

    @field_validator("splits")
    @classmethod
    def validate_splits(cls, value: object) -> dict[str, float] | None:
        return _validate_splits(value)

    @model_validator(mode="after")
    def check_splits_sum(self) -> "ExpenseCreate":
        _ensure_splits_match_amount(self.splits, self.amount)
        return self


class ExpenseUpdate(BaseModel):
    """Vollstaendige Aktualisierung einer Ausgabe (PUT).

    Enthaelt bewusst ALLE bearbeitbaren Felder inkl. ``receipt_date`` — das
    Bearbeiten-Formular schickt sie vollstaendig. Fehlt das Datum, wird es
    geleert (``None``).
    """

    title: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0)
    payer_name: str = Field(min_length=1, max_length=100)
    split_ratio: float = Field(default=0.5, ge=0.0, le=1.0)
    category: str = Field(min_length=1, max_length=100)
    receipt_date: date | None = None
    # Erfassungswaehrung (der Kurs wird beim Speichern serverseitig neu ermittelt)
    currency: str = "EUR"
    # Advanced Split (Roadmap 3.0 #3): explizite Pro-Person-Aufteilung
    # {Name: Betrag}. None → Aufteilung entfernen, Fallback auf split_ratio.
    splits: dict[str, float] | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: object) -> str:
        return _normalize_currency(value)

    @field_validator("splits")
    @classmethod
    def validate_splits(cls, value: object) -> dict[str, float] | None:
        return _validate_splits(value)

    @model_validator(mode="after")
    def check_splits_sum(self) -> "ExpenseUpdate":
        _ensure_splits_match_amount(self.splits, self.amount)
        return self


class ExpenseResponse(BaseModel):
    """Response-Form einer Ausgabe (aus dem ORM-Objekt serialisiert)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    list_id: uuid.UUID
    title: str
    amount: float
    payer_name: str
    split_ratio: float
    category: str
    created_at: datetime
    # Nur bei gescannten Bons gesetzt (siehe ExpenseCreate.receipt_date)
    receipt_date: date | None = None
    # Multi-Currency: Erfassungswaehrung + Tageskurs (EUR je 1 Einheit currency).
    # Der EUR-Betrag ergibt sich im Frontend als amount * exchange_rate.
    currency: str = "EUR"
    exchange_rate: float = 1.0
    # Advanced Split (Roadmap 3.0 #3): Pro-Person-Aufteilung {Name: Betrag} in der
    # Erfassungswaehrung, oder None (dann gilt split_ratio als Fallback).
    splits: dict[str, float] | None = None


# ---------- Listen ----------

class SharedListCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class SharedListResponse(BaseModel):
    """Response einer Liste inklusive aller zugehoerigen Ausgaben."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    expenses: list[ExpenseResponse] = []


# ---------- Kassenbon-Analyse (Ollama) ----------

class ReceiptAnalysis(BaseModel):
    """Das JSON, das die Vision-KI für einen Kassenbon liefern muss.

    Das Modell liefert das Kaufdatum unter dem JSON-Key ``date``; intern heisst
    das Feld ``receipt_date`` (per Alias), damit der Bezeichner nicht den
    importierten ``date``-Typ verschattet.
    """

    model_config = ConfigDict(populate_by_name=True)

    title: str
    amount: float = Field(gt=0)
    # Kaufdatum vom Bon. Wird zwingend angefragt, aber tolerant behandelt:
    # ist es unlesbar, bleibt es None (der Scan schlaegt deshalb NICHT fehl).
    receipt_date: date | None = Field(default=None, alias="date")
    category: str
    # Waehrung vom Bon (Roadmap 2.0 #3). Tolerant: Unbekanntes/Fehlendes faellt
    # auf EUR zurueck, damit der Scan nicht an der Waehrung scheitert.
    currency: str = "EUR"

    @field_validator("amount", mode="before")
    @classmethod
    def parse_german_amount(cls, value: object) -> object:
        # Vision-Modelle liefern den Betrag trotz Prompt gern als String
        # wie "24,50" oder "24,50 €" — das hier rettet solche Antworten
        if isinstance(value, str):
            return value.replace("€", "").replace("EUR", "").strip().replace(",", ".")
        return value

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_or_fallback_currency(cls, value: object) -> str:
        # Nicht unterstuetzte/leere Waehrung → EUR (Scan bleibt robust)
        if value is None:
            return "EUR"
        code = str(value).strip().upper()
        return code if code in SUPPORTED_CURRENCIES else "EUR"

    @field_validator("receipt_date", mode="before")
    @classmethod
    def parse_receipt_date(cls, value: object) -> date | None:
        # Toleriert ISO, deutsches TT.MM.JJJJ und angehaengte Uhrzeiten
        return _parse_flexible_date(value)


# ---------- Kassensturz / Settlement (N Personen) ----------

class SettlementTransaction(BaseModel):
    """Eine einzelne Ausgleichszahlung: ``from_person`` zahlt an ``to_person``."""

    from_person: str
    to_person: str
    amount: float


class PersonBalance(BaseModel):
    """Zwischenstand einer Person nach allen Ausgaben.

    ``net`` > 0 → die Person bekommt Geld (hat mehr ausgelegt als verbraucht),
    ``net`` < 0 → die Person schuldet Geld.
    """

    name: str
    paid: float
    share: float
    net: float


class SettlementResponse(BaseModel):
    """Kompletter Kassensturz: Salden je Person + minimale Ausgleichszahlungen."""

    balances: list[PersonBalance] = []
    transactions: list[SettlementTransaction] = []


# ---------- Kategorie-Regeln (Kontoauszug-Import, Roadmap 4.0 #3) ----------

class CategoryRuleCreate(BaseModel):
    """Request-Body zum Anlegen/Lernen einer Kategorie-Regel.

    ``recipient_keyword`` wird getrimmt und grossgeschrieben gespeichert, damit
    der spaetere Abgleich mit Kontoauszugs-Empfaengern case-insensitive ist.
    """

    recipient_keyword: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)

    @field_validator("recipient_keyword")
    @classmethod
    def normalize_keyword(cls, value: str) -> str:
        return value.strip().upper()


class CategoryRuleResponse(BaseModel):
    """Response-Form einer Kategorie-Regel (aus dem ORM-Objekt serialisiert)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    list_id: uuid.UUID
    recipient_keyword: str
    category: str


# ---------- Bon-Scan-Status (Receipt-Jobs, Bugfix 2026-09-25) ----------

class ReceiptUploadResponse(BaseModel):
    """Sofort-Antwort (HTTP 202) des asynchronen Bon-Uploads."""

    status: str
    job_id: uuid.UUID


class ReceiptJobResponse(BaseModel):
    """Status eines Bon-Scans — vom Frontend per Polling abgefragt."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    list_id: uuid.UUID
    payer_name: str
    filename: str | None = None
    status: str  # "processing" | "done" | "failed"
    detail: str | None = None
    error: str | None = None
    expense_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


# ---------- Kontoauszug-Import (Epic 4.0 #3) ----------

class BankTransaction(BaseModel):
    """Eine aus dem Kontoauszug gelesene Buchung (Vorschau, noch nicht gespeichert).

    ``amount`` ist **negativ bei Ausgaben**, positiv bei Einnahmen. Die Felder
    ``category``/``is_food`` sind das Ergebnis der Kategorisierung (Stufe 1 der
    spaeteren Komplettanalyse: bisher nur Lebensmittel).
    """

    index: int
    booking_date: date | None = None
    description: str
    amount: float
    category: str | None = None
    # Anzeigename des Treffers (z. B. "Rewe") — Vorschlag fuer den Ausgaben-Titel
    label: str | None = None
    is_food: bool = False
    # Es gibt in der Liste schon eine Ausgabe mit gleichem Betrag am selben Tag
    duplicate: bool = False
    # Vorzeichen war im PDF nicht erkennbar (wurde angenommen)
    sign_guessed: bool = False


class BankStatementPreview(BaseModel):
    """Antwort von ``POST …/bank-statement/parse``: alle erkannten Buchungen."""

    transactions: list[BankTransaction]
    warnings: list[str] = []


class BankImportItem(BaseModel):
    """Eine zu uebernehmende Buchung (positiver Betrag, immer EUR)."""

    title: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0)
    booking_date: date | None = None


class BankImportRequest(BaseModel):
    """Request-Body von ``POST …/bank-statement/import``."""

    payer_name: str = Field(min_length=1, max_length=100)
    category: str = Field(default="Lebensmittel", min_length=1, max_length=100)
    items: list[BankImportItem] = Field(min_length=1, max_length=500)


class BankImportResponse(BaseModel):
    created: int
    total: float

