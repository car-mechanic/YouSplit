"""Kontoauszug-Parser (Epic 4.0 #3): PDF → Buchungen → Lebensmittel-Erkennung.

Bewusst **ohne** DB-/FastAPI-Bezug (nur ``pdfplumber`` fuer den PDF-Text), damit
die Logik testbar bleibt und spaeter fuer die Komplettanalyse aller Buchungen
wiederverwendbar ist (siehe AI_CONTEXT.md, Abschnitt 4.5 #5).

Ansatz — **generisch fuer mehrere deutsche Banken**, kein bankspezifisches
Layout:

1. ``extract_lines``: Text je Seite zeilenweise aus dem PDF lesen.
2. ``parse_lines``: Eine Buchung beginnt mit einer Zeile, die mit einem Datum
   (``TT.MM.`` / ``TT.MM.JJ`` / ``TT.MM.JJJJ``) startet. Folgezeilen ohne Datum
   gehoeren zum Verwendungszweck. Der Betrag ist der deutsche Dezimalbetrag
   (``1.234,56``) mit Vorzeichen vorn/hinten (``-12,34`` / ``12,34-``) oder
   Soll/Haben-Kennzeichen (``S``/``H``).
3. ``classify``: Lebensmittel-Erkennung ueber (a) gelernte ``CategoryRule``-
   Stichwoerter der Liste (haben Vorrang) und (b) die Haendlerliste
   ``food_merchants.txt`` (von Hand erweiterbar, siehe Kopf der Datei).

Grenzen (generischer Parser!): Ohne Beispiel-PDF der konkreten Bank kann das
Layout im Einzelfall nicht passen — deshalb zeigt das Frontend vor dem Import
immer eine Vorschau. Gescannte (Bild-)PDFs enthalten keinen Text und werden
nicht unterstuetzt.
"""

import io
import logging
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

logger = logging.getLogger("yousplit.bankstatement")

CATEGORY_FOOD = "Lebensmittel"

# Schutz vor riesigen/missbrauchten Uploads.
MAX_PAGES = 80

# Haendlerliste: eigene, von Hand pflegbare Textdatei neben diesem Modul. Sie wird
# bei Bedarf neu gelesen (Aenderung der Datei genuegt, kein Neustart). Format und
# Bedienung stehen im Kopf der Datei selbst.
FOOD_MERCHANTS_FILE = Path(__file__).with_name("food_merchants.txt")

# ---------------------------------------------------------------------------
# Regex-Bausteine
# ---------------------------------------------------------------------------

# Datum am Zeilenanfang: TT.MM. | TT.MM.JJ | TT.MM.JJJJ
_DATE_RE = re.compile(r"\s*(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})?(?!\d)")

# Deutscher Betrag: 1.234,56 | 12,34 — Vorzeichen DIREKT davor/dahinter oder
# Soll/Haben-Kennzeichen (S/H, ggf. mit Leerzeichen); optional EUR/€-Suffix.
_AMOUNT_RE = re.compile(
    r"(?<![\w.,])"
    r"(?P<lead>[+-]?)"
    r"(?P<int>\d{1,3}(?:\.\d{3})+|\d+),(?P<dec>\d{2})(?!\d)"
    r"(?P<trail>[+-]|\s?[SH](?![A-Za-z0-9]))?"
    r"(?:\s?(?:EUR|€))?"
)

# Dated Zeilen mit diesen Woertern sind Salden/Uebertraege, keine Buchungen.
_BALANCE_RE = re.compile(r"KONTOSTAND|SALDO|ÜBERTRAG|UEBERTRAG", re.IGNORECASE)
# Nicht-datierte Zeilen, die eine Buchung beenden (Seitenfuss/-kopf, Salden).
_BLOCK_END_RE = re.compile(
    r"KONTOSTAND|SALDO|ÜBERTRAG|UEBERTRAG|KONTOAUSZUG|\bSEITE\s*\d", re.IGNORECASE
)
# Ohne Vorzeichen: diese Woerter deuten auf eine Gutschrift (Einnahme) hin.
_CREDIT_HINTS = (
    "GUTSCHRIFT",
    "GEHALT",
    "LOHN",
    "EINZAHLUNG",
    "ERSTATTUNG",
    "RUECKERSTATTUNG",
    "ZINSEN",
    "EINGANG",
)

_FOLD_TABLE = str.maketrans({"Ä": "AE", "Ö": "OE", "Ü": "UE", "ß": "SS"})


class StatementParseError(Exception):
    """Der Kontoauszug konnte nicht gelesen werden (nutzerverstaendliche Ursache)."""


@dataclass
class Booking:
    """Eine Buchung des Kontoauszugs. ``amount`` ist **negativ bei Ausgaben**."""

    booking_date: date | None
    description: str
    amount: float
    # Vorzeichen war im PDF nicht erkennbar (Betrag ohne +/-/S/H) → Annahme.
    sign_guessed: bool = False


@dataclass
class ParseResult:
    bookings: list[Booking]
    warnings: list[str] = field(default_factory=list)


@dataclass
class Classification:
    """Ergebnis der Kategorisierung einer Buchung."""

    category: str | None  # None = nicht erkannt
    label: str | None  # Haendler-/Stichwort-Anzeigename (Titel der Ausgabe)

    @property
    def is_food(self) -> bool:
        return self.category == CATEGORY_FOOD


# ---------------------------------------------------------------------------
# 1) PDF → Zeilen
# ---------------------------------------------------------------------------


def extract_lines(pdf_bytes: bytes) -> list[str]:
    """Liest den Text aller Seiten und liefert ihn zeilenweise.

    Raises:
        StatementParseError: PDF nicht lesbar, verschluesselt oder ohne Text
            (z. B. eingescannt).
    """
    # Lazy-Import: fehlt pdfplumber (z. B. Backend-Image noch nicht neu gebaut),
    # darf NUR der Kontoauszug-Import ausfallen — nicht der ganze Backend-Start.
    try:
        import pdfplumber
    except ImportError as exc:
        raise StatementParseError(
            "Die PDF-Bibliothek fehlt im Backend. Bitte einmal "
            "`docker compose up --build` ausführen."
        ) from exc

    lines: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if len(pdf.pages) > MAX_PAGES:
                raise StatementParseError(
                    f"Das PDF hat zu viele Seiten (max. {MAX_PAGES})."
                )
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines.extend(text.splitlines())
    except StatementParseError:
        raise
    except Exception as exc:  # noqa: BLE001 — pdfplumber/pdfminer werfen vielerlei
        logger.warning("PDF nicht lesbar: %s", exc)
        raise StatementParseError(
            "Das PDF konnte nicht gelesen werden (beschädigt oder passwortgeschützt?)."
        ) from exc

    if not any(line.strip() for line in lines):
        raise StatementParseError(
            "Im PDF wurde kein Text gefunden — vermutlich ein eingescannter "
            "Kontoauszug. Bitte das PDF direkt aus dem Online-Banking laden."
        )
    return lines


# ---------------------------------------------------------------------------
# 2) Zeilen → Buchungen
# ---------------------------------------------------------------------------


def _parse_german_amount(match: re.Match[str]) -> tuple[float, bool | None]:
    """Betrag + Vorzeichen eines Treffers. Zweiter Wert: True = Ausgabe,
    False = Einnahme, None = nicht erkennbar."""
    value = float(match.group("int").replace(".", "") + "." + match.group("dec"))
    lead = match.group("lead")
    trail = (match.group("trail") or "").strip()
    if lead == "-" or trail in ("-", "S"):
        return value, True
    if lead == "+" or trail in ("+", "H"):
        return value, False
    return value, None


def _to_date(day: str, month: str, year: str | None, default_year: int) -> date | None:
    """Baut ein Datum; zweistellige Jahre → 20xx; fehlendes Jahr → ``default_year``."""
    if year is None:
        y = default_year
    elif len(year) == 2:
        y = 2000 + int(year)
    else:
        y = int(year)
    try:
        return date(y, int(month), int(day))
    except ValueError:
        return None


def _infer_year(lines: list[str]) -> int:
    """Haeufigstes Jahr aus vollstaendigen Datumsangaben des Dokuments (Fallback:
    laufendes Jahr). Noetig fuer Banken, die Buchungen nur als ``TT.MM.`` listen."""
    years = Counter(
        int(m.group(1))
        for line in lines
        for m in re.finditer(r"\d{1,2}\.\d{1,2}\.(20\d{2})(?!\d)", line)
    )
    if years:
        return years.most_common(1)[0][0]
    return date.today().year


def _strip_leading_dates(text: str) -> tuple[re.Match[str] | None, str]:
    """Trennt ein fuehrendes Datum (und ein direkt folgendes zweites, z. B. die
    Wertstellung) vom Rest der Zeile ab."""
    first = _DATE_RE.match(text)
    if first is None:
        return None, text
    rest = text[first.end():]
    second = _DATE_RE.match(rest)
    if second is not None:
        rest = rest[second.end():]
    return first, rest.strip()


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class _Block:
    """Zwischenzustand einer Buchung waehrend des Zeilen-Scans."""

    first_date: tuple[str, str, str | None] | None
    first_text: str
    extra: list[str] = field(default_factory=list)
    # Betrag aus der ersten Zeile (falls dort vorhanden)
    amount_match: re.Match[str] | None = None


def parse_lines(lines: list[str]) -> ParseResult:
    """Erkennt Buchungen in den Textzeilen eines Kontoauszugs (generisch)."""
    warnings: list[str] = []
    default_year = _infer_year(lines)
    # Banken mit Betrags- UND Saldospalte: dann ist der Betrag der vorletzte.
    balance_column = any(
        re.search(r"\bBETRAG\b", line, re.IGNORECASE)
        and re.search(r"\bSALDO\b", line, re.IGNORECASE)
        for line in lines
    )

    blocks: list[_Block] = []
    current: _Block | None = None

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        date_match, rest = _strip_leading_dates(line)

        if date_match is not None:
            valid = _to_date(
                date_match.group(1),
                date_match.group(2),
                date_match.group(3),
                default_year,
            )
            if valid is None:
                # Sieht nur wie ein Datum aus (z. B. "99.99.") → Fliesstext
                date_match = None

        if date_match is None:
            # Folgezeile: gehoert zur offenen Buchung, ausser sie ist Seitenkopf/-fuss
            if current is None:
                continue
            if _BLOCK_END_RE.search(line):
                current = None
                continue
            current.extra.append(line)
            continue

        # Datierte Zeile
        if _BALANCE_RE.search(rest):
            current = None  # Saldo-/Uebertragszeile, keine Buchung
            continue

        amounts = list(_AMOUNT_RE.finditer(rest))
        if not amounts and current is not None and current.amount_match is not None:
            # z. B. ING: zweite Zeile mit Valuta-Datum, aber ohne Betrag → Fortsetzung
            current.extra.append(rest)
            continue

        chosen: re.Match[str] | None = None
        if amounts:
            chosen = amounts[-2] if (balance_column and len(amounts) >= 2) else amounts[-1]

        current = _Block(
            first_date=(
                date_match.group(1),
                date_match.group(2),
                date_match.group(3),
            ),
            first_text=rest,
            amount_match=chosen,
        )
        blocks.append(current)

    bookings: list[Booking] = []
    skipped_without_amount = 0
    any_guessed = False

    # Vorzeichen-Konvention des Dokuments: Zeigt das PDF Ausgaben explizit mit
    # Minus (Sparkasse: "-45,67"), aber keine explizit markierten Einnahmen
    # ("+"/"H"), dann sind Betraege OHNE Vorzeichen Gutschriften.
    explicit = [
        _parse_german_amount(b.amount_match)[1]
        for b in blocks
        if b.amount_match is not None
    ]
    unsigned_is_credit = (True in explicit) and (False not in explicit)

    for block in blocks:
        match = block.amount_match
        description_parts: list[str] = []

        if match is not None:
            before = block.first_text[: match.start()]
            after = block.first_text[match.end():]
            description_parts.append(f"{before} {after}")
        else:
            description_parts.append(block.first_text)
            # Betrag steht auf einer Folgezeile: erste fast reine Betragszeile,
            # sonst der letzte Betrag im Block.
            fallback: tuple[int, re.Match[str]] | None = None
            for index, extra in enumerate(block.extra):
                found = list(_AMOUNT_RE.finditer(extra))
                if not found:
                    continue
                candidate = found[-1]
                leftover = (extra[: candidate.start()] + extra[candidate.end():]).strip()
                if len(leftover) <= 3:
                    fallback = (index, candidate)
                    break
                fallback = (index, candidate)
            if fallback is not None:
                index, match = fallback
                extra = block.extra[index]
                block.extra[index] = extra[: match.start()] + extra[match.end():]

        if match is None:
            skipped_without_amount += 1
            continue

        description_parts.extend(block.extra)
        description = _normalize(" ".join(description_parts))
        amount, is_expense = _parse_german_amount(match)

        guessed = False
        if is_expense is None:
            if unsigned_is_credit:
                is_expense = False
            else:
                guessed = True
                folded = _fold(description)
                is_expense = not any(hint in folded for hint in _CREDIT_HINTS)
                any_guessed = True

        d = block.first_date
        booking_date = _to_date(d[0], d[1], d[2], default_year) if d else None
        # Jahreswechsel: Auszug Dez→Jan ohne Jahr in den Buchungen — ein Dezember-
        # Datum in einem Dokument, das ueberwiegend Januar-Buchungen hat, gehoert
        # zum Vorjahr. Wird unten nachkorrigiert.
        bookings.append(
            Booking(
                booking_date=booking_date,
                description=description,
                amount=-abs(amount) if is_expense else abs(amount),
                sign_guessed=guessed,
            )
        )

    _fix_year_wrap(bookings, lines)

    if skipped_without_amount:
        warnings.append(
            f"{skipped_without_amount} Zeile(n) mit Datum, aber ohne erkennbaren "
            "Betrag wurden übersprungen."
        )
    if any_guessed:
        warnings.append(
            "Bei manchen Buchungen war das Vorzeichen im PDF nicht erkennbar — "
            "sie wurden als Ausgabe gewertet (außer bei Wörtern wie Gutschrift/"
            "Gehalt). Bitte in der Vorschau prüfen."
        )
    if not bookings:
        warnings.append("Es wurden keine Buchungen erkannt.")
    return ParseResult(bookings=bookings, warnings=warnings)


def _fix_year_wrap(bookings: list[Booking], lines: list[str]) -> None:
    """Jahreswechsel-Korrektur fuer Auszuege ohne Jahr in den Buchungszeilen.

    Greift nur, wenn das Jahr aus den Kopfzeilen abgeleitet wurde und der Auszug
    Dezember- UND Januar-Buchungen enthaelt: Dezember-Buchungen liegen dann im
    Vorjahr der Januar-Buchungen.
    """
    dated = [b for b in bookings if b.booking_date is not None]
    months = {b.booking_date.month for b in dated if b.booking_date}
    if not (12 in months and 1 in months):
        return
    # Nur anfassen, wenn KEINE Zeile ein explizites Jahr in der Buchung traegt.
    explicit = any(
        re.match(r"\s*\d{1,2}\.\d{1,2}\.\d{2,4}(?!\d)", line) for line in lines
    )
    if explicit:
        return
    for booking in dated:
        d = booking.booking_date
        if d is not None and d.month == 12:
            booking.booking_date = date(d.year - 1, 12, d.day)


# ---------------------------------------------------------------------------
# 3) Kategorisierung (Lebensmittel)
# ---------------------------------------------------------------------------


def _fold(text: str) -> str:
    """Normalisiert Text fuer den Stichwort-Abgleich: GROSSBUCHSTABEN, Umlaute/ß
    aufgeloest (Ä→AE), Akzente entfernt (É→E), alle Sonderzeichen/Folgen davon
    zu einem Leerzeichen. So sind "E-Center", "E CENTER" und "e.center" gleich und
    "PayPal *LIDL SAGT DANKE" wird zu "PAYPAL LIDL SAGT DANKE"."""
    upper = text.upper().translate(_FOLD_TABLE)
    stripped = "".join(
        ch
        for ch in unicodedata.normalize("NFKD", upper)
        if not unicodedata.combining(ch)
    )
    return re.sub(r"[^A-Z0-9]+", " ", stripped).strip()


@dataclass(frozen=True)
class MerchantEntry:
    """Ein Eintrag der Haendlerliste (Stichwort bereits mit ``_fold`` normalisiert)."""

    keyword: str
    # True = auch als Teil eines laengeren Worts treffen ("*FLEISCHEREI" findet
    # "LANDFLEISCHEREI"); False = nur als ganzes Wort/ganze Wortfolge.
    substring: bool = False


def parse_merchant_lines(lines: list[str]) -> list[MerchantEntry]:
    """Liest die Zeilen der Haendlerliste (``food_merchants.txt``).

    ``#`` leitet einen Kommentar ein (auch am Zeilenende), leere Zeilen werden
    ignoriert, ein fuehrender ``*`` markiert einen Teilwort-Treffer. Doppelte
    Eintraege werden verworfen.
    """
    entries: list[MerchantEntry] = []
    seen: set[tuple[str, bool]] = set()
    for raw in lines:
        text = raw.split("#", 1)[0].strip()
        if not text:
            continue
        substring = text.startswith("*")
        keyword = _fold(text.lstrip("*"))
        if not keyword or (keyword, substring) in seen:
            continue
        seen.add((keyword, substring))
        entries.append(MerchantEntry(keyword=keyword, substring=substring))
    return entries


# Cache je Datei: (mtime, Eintraege) — Datei wird nur neu gelesen, wenn sie
# veraendert wurde (der Upload ruft classify() je Buchung auf).
_merchant_cache: dict[str, tuple[float, list[MerchantEntry]]] = {}


def load_food_merchants(path: Path = FOOD_MERCHANTS_FILE) -> list[MerchantEntry]:
    """Haendlerliste laden (mit mtime-Cache). Fehlt die Datei, wird geloggt und
    eine leere Liste genutzt — der Import laeuft dann nur mit den CategoryRules."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        logger.warning("Haendlerliste nicht gefunden: %s", path)
        return []

    cached = _merchant_cache.get(str(path))
    if cached is not None and cached[0] == mtime:
        return cached[1]

    entries = parse_merchant_lines(path.read_text(encoding="utf-8").splitlines())
    _merchant_cache[str(path)] = (mtime, entries)
    logger.info("Haendlerliste geladen: %d Eintraege (%s)", len(entries), path.name)
    return entries


def _match(folded_text: str, entry: MerchantEntry) -> str | None:
    """Trifft der Eintrag auf den normalisierten Text? Rueckgabe: das gefundene
    Wort (bei Teilwort-Treffer das ganze umgebende Wort, z. B. "LANDFLEISCHEREI")
    bzw. das Stichwort selbst — als Basis fuer den Anzeigenamen."""
    if not entry.substring:
        if f" {entry.keyword} " in f" {folded_text} ":
            return entry.keyword
        return None
    index = folded_text.find(entry.keyword)
    if index < 0:
        return None
    start = folded_text.rfind(" ", 0, index) + 1
    end = folded_text.find(" ", index)
    return folded_text[start : end if end != -1 else len(folded_text)]


# Anzeigenamen: aus dem normalisierten Text lassen sich Umlaute nicht zurueck-
# gewinnen — die haeufigsten Faelle werden hier huebsch gemacht.
_DISPLAY_FIXES = (
    ("Baeck", "Bäck"),
    ("Getraenk", "Getränk"),
    ("Gemuese", "Gemüse"),
    ("Brueck", "Brück"),
)


def _display_name(word: str) -> str:
    title = word.title()
    for plain, pretty in _DISPLAY_FIXES:
        title = title.replace(plain, pretty)
    return title


def classify(
    description: str, rules: list[tuple[str, str]] | None = None
) -> Classification:
    """Ordnet eine Buchung einer Kategorie zu.

    ``rules`` sind die gelernten ``CategoryRule``-Paare ``(Stichwort, Kategorie)``
    der Liste. Sie haben **Vorrang** vor der Haendlerliste ``food_merchants.txt``
    (so kann ein Nutzer z. B. "REWE" bewusst anders einordnen); bei mehreren
    Treffern gewinnt das laengste Stichwort. Ohne Treffer: ``category=None``.
    """
    folded = _fold(description)

    best_rule: tuple[str, str] | None = None
    for keyword, category in rules or []:
        normalized = _fold(keyword)
        if normalized and f" {normalized} " in f" {folded} ":
            if best_rule is None or len(normalized) > len(best_rule[0]):
                best_rule = (normalized, category)
    if best_rule is not None:
        return Classification(
            category=best_rule[1], label=_display_name(best_rule[0])
        )

    best: tuple[int, str] | None = None
    for entry in load_food_merchants():
        word = _match(folded, entry)
        if word is not None and (best is None or len(entry.keyword) > best[0]):
            best = (len(entry.keyword), word)
    if best is not None:
        return Classification(category=CATEGORY_FOOD, label=_display_name(best[1]))
    return Classification(category=None, label=None)


# ---------------------------------------------------------------------------
# Komfort-Einstieg
# ---------------------------------------------------------------------------


def parse_statement(pdf_bytes: bytes) -> ParseResult:
    """PDF-Bytes → erkannte Buchungen (+ Warnungen)."""
    return parse_lines(extract_lines(pdf_bytes))
