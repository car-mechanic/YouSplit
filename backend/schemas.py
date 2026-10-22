import math
import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from currency import SUPPORTED_CURRENCIES
from ha_identity import MAX_USER_ID_LENGTH

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
        # NaN/Infinity kaemen sonst durch (nan < 0 ist False) und wuerden den
        # Kassensturz der ganzen Liste auf NaN ziehen.
        if not math.isfinite(amount) or amount < 0:
            raise ValueError(
                f"splits-Betrag fuer '{key}' muss eine endliche Zahl >= 0 sein"
            )
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


def _text(max_length: int):
    """Pflichttext ohne Leerzeichen am Rand. Sonst waere 'Kev ' im Kassensturz
    eine zweite Person neben 'Kev' und ein Titel aus Leerzeichen gueltig."""
    return Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)
    ]


Title = _text(200)
PersonName = _text(100)
Category = _text(100)


# ---------- Expenses ----------

class ExpenseCreate(BaseModel):
    """Request-Body zum Anlegen einer Ausgabe."""

    title: Title
    amount: float = Field(gt=0, allow_inf_nan=False)
    payer_name: PersonName
    split_ratio: float = Field(default=0.5, ge=0.0, le=1.0)
    category: Category = "Unknown/Manuell"
    # Ausgabedatum (Datum auf dem Bon bzw. der Buchung). Grundlage der
    # Duplikats-Pruefung; ``None`` = Anlagetag.
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

    title: Title
    amount: float = Field(gt=0, allow_inf_nan=False)
    payer_name: PersonName
    split_ratio: float = Field(default=0.5, ge=0.0, le=1.0)
    category: Category
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
    # Ausgabedatum (siehe ExpenseCreate.receipt_date); bei Altdaten None
    receipt_date: date | None = None
    # Multi-Currency: Erfassungswaehrung + Tageskurs (EUR je 1 Einheit currency).
    # Der EUR-Betrag ergibt sich im Frontend als amount * exchange_rate.
    currency: str = "EUR"
    exchange_rate: float = 1.0
    # Advanced Split (Roadmap 3.0 #3): Pro-Person-Aufteilung {Name: Betrag} in der
    # Erfassungswaehrung, oder None (dann gilt split_ratio als Fallback).
    splits: dict[str, float] | None = None


# ---------- Listen ----------

MAX_MEMBERS = 50


def _normalize_members(value: list[str]) -> list[str]:
    """Namen trimmen, Leere weglassen, Doppelte (gleiche Schreibweise) entfernen.

    Die Reihenfolge bleibt: sie ist die Reihenfolge im Splitter und Kassensturz.
    """
    members: list[str] = []
    for raw in value:
        name = raw.strip()
        if not name or name in members:
            continue
        if len(name) > 100:
            raise ValueError(f"Name zu lang (max. 100 Zeichen): '{name[:20]}…'")
        members.append(name)
    return members


class SharedListCreate(BaseModel):
    title: Title


class MembersUpdate(BaseModel):
    """Request-Body von ``PUT /lists/{id}/members``: die Personen der Liste.

    ``member_users`` verknuepft Personen mit Home-Assistant-Benutzern
    ({Name: Benutzer-ID}). Ein Benutzer ist hoechstens eine Person der Liste,
    sonst waere „Wer bin ich?“ mehrdeutig.
    """

    members: list[str] = Field(max_length=MAX_MEMBERS)
    member_users: dict[str, str] = {}

    @field_validator("members")
    @classmethod
    def normalize(cls, value: list[str]) -> list[str]:
        return _normalize_members(value)

    @model_validator(mode="after")
    def check_member_users(self) -> "MembersUpdate":
        links: dict[str, str] = {}
        for raw_name, raw_user_id in self.member_users.items():
            name, user_id = raw_name.strip(), raw_user_id.strip()
            if name not in self.members:
                raise ValueError(f"'{name}' ist keine Person der Liste")
            if not user_id or len(user_id) > MAX_USER_ID_LENGTH:
                raise ValueError(f"Ungültige Benutzer-ID für '{name}'")
            if user_id in links.values():
                raise ValueError("Ein Benutzer ist mehreren Personen zugeordnet")
            links[name] = user_id
        self.member_users = links
        return self


class SharedListResponse(BaseModel):
    """Response einer Liste inklusive aller zugehoerigen Ausgaben."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    # Feste Personen der Liste (leer bei Altlisten ohne Tutorial)
    members: list[str] = []
    # Person → Home-Assistant-Benutzer-ID (siehe MembersUpdate)
    member_users: dict[str, str] = {}
    expenses: list[ExpenseResponse] = []

    @field_validator("members", mode="before")
    @classmethod
    def none_as_empty(cls, value: object) -> object:
        return [] if value is None else value

    @field_validator("member_users", mode="before")
    @classmethod
    def none_as_empty_dict(cls, value: object) -> object:
        return {} if value is None else value


# ---------- Home-Assistant-Benutzer ----------

class CurrentUser(BaseModel):
    """Der über Ingress angemeldete Home-Assistant-Benutzer."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    display_name: str


class HaUserOption(BaseModel):
    """Ein auswählbarer Home-Assistant-Benutzer (Personen-Auswahl)."""

    id: str
    name: str


class MyList(BaseModel):
    """Eine Liste in „Meine Listen“ (Startseite, geräteübergreifend)."""

    id: uuid.UUID
    title: str
    # Letzter Besuch dieses Benutzers; None = nur als Person verknüpft
    last_visit: datetime | None
    # Der Benutzer ist als Person der Liste verknüpft (dann nicht entfernbar)
    is_member: bool


class BookmarkImport(BaseModel):
    """Übernahme der lokal gemerkten Listen eines Geräts in „Meine Listen“."""

    list_ids: list[uuid.UUID] = Field(max_length=100)


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

    recipient_keyword: Title
    category: Category

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

    title: Title
    amount: float = Field(gt=0, allow_inf_nan=False)
    booking_date: date | None = None


class BankImportRequest(BaseModel):
    """Request-Body von ``POST …/bank-statement/import``."""

    payer_name: PersonName
    category: Category = "Lebensmittel"
    items: list[BankImportItem] = Field(min_length=1, max_length=500)


class BankImportResponse(BaseModel):
    created: int
    total: float

