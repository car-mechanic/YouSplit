import asyncio
import base64
import io
import logging
import os
import time

import httpx
from PIL import Image, ImageOps
from pydantic import ValidationError

from categories import DEFAULT_CATEGORIES, FALLBACK_CATEGORY, LEGACY_ALIASES
from schemas import ReceiptAnalysis

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
# qwen2.5vl:3b ist auf CPU spuerbar schneller als die neueren Qwen3.x-Modelle:
# Der Test mit qwen3.5:2b (2026-10-02) dauerte deutlich laenger pro Bon; auf dem
# Ollama-Tracker gibt es Berichte, dass Qwen3-VL/Qwen3.5 dort langsamer laufen
# als Qwen2.5-VL. Ein Wechsel aendert nur diese eine Einstellung.
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5vl:3b")

# Modelle der Qwen3-Familie "denken" standardmaessig erst laenger nach, bevor sie
# antworten. Nur fuer sie wird das Denken explizit abgeschaltet.
THINKING_MODEL_PREFIXES = ("qwen3",)


def thinking_options(model: str) -> dict:
    """Zusatzfelder fuer den Chat-Aufruf: ``think: false`` bei Denk-Modellen.

    Fuer andere Modelle (z. B. qwen2.5vl) wird das Feld bewusst NICHT gesendet —
    sie kennen keinen Denkmodus, und ein unbekanntes Feld soll keinen Scan
    gefaehrden.
    """
    if model.lower().startswith(THINKING_MODEL_PREFIXES):
        return {"think": False}
    return {}

# Beim ersten Request nach einem (Neu-)Start muss Ollama das ~8-GB-Modell
# erst in den RAM laden — auf CPU-Hardware dauert Laden + Analyse zusammen
# mehrere Minuten.
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "300"))
# Einmaliger Modell-Download (~3 GB) — je nach Leitung deutlich laenger als ein
# Scan. Grosszuegig bemessen; der Download laeuft ohnehin im Hintergrund.
OLLAMA_PULL_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_PULL_TIMEOUT_SECONDS", "3600"))

logger = logging.getLogger("yousplit.ollama")

# Der Prompt ist bewusst ausfuehrlich: Im OCR-Haertetest (Roadmap 2.0 #1) las das
# Modell Titel, Betrag und Kategorie zuverlaessig, lieferte das Datum aber als
# null — obwohl es (deutsch als TT.MM.JJJJ) klar auf dem Bon stand. Darum jetzt
# explizit: WO das Datum steht, dass es fast immer vorhanden ist und WIE es nach
# YYYY-MM-DD umzuwandeln ist. (Der schema-seitige Parser toleriert zusaetzlich
# deutsche Formate — der Prompt soll aber schon sauber liefern.)
RECEIPT_PROMPT = (
    "Du bist ein praeziser Parser fuer Kassenbons. Extrahiere ZWINGEND diese "
    "vier Werte:\n"
    "1) 'title': Name des Geschaefts bzw. Supermarkts (z.B. 'Lidl', 'Edeka', "
    "'Rewe', 'dm').\n"
    "2) 'amount': den ZU ZAHLENDEN Gesamtbetrag als Float (z.B. 137.77). Das ist "
    "die Endsumme neben 'zu zahlen', 'Summe', 'Gesamt', 'Total' oder 'Betrag' — "
    "NIEMALS ein einzelner Artikelpreis oder ein Zwischenwert.\n"
    "3) 'date': das Kaufdatum. Auf FAST JEDEM Bon steht ein Datum, meist in der "
    "Naehe von Uhrzeit, Kassen-/Beleg-Nummer oder der Zahlung, ueblicherweise "
    "deutsch als TT.MM.JJJJ (z.B. 05.12.2025) oder TT.MM.JJ (z.B. 05.12.25). "
    "Suche es sorgfaeltig und gib es IMMER im Format YYYY-MM-DD zurueck "
    "(Beispiel: 05.12.2025 wird zu 2025-12-05; 05.12.25 wird zu 2025-12-05). "
    "Nur wenn WIRKLICH kein Datum lesbar ist, setze 'date' auf null.\n"
    f"4) 'category': GENAU eine aus dieser Liste: {', '.join(DEFAULT_CATEGORIES)}. "
    "Rate keine anderen Werte.\n"
    "5) 'currency': die Waehrung des Bons als 3-Buchstaben-Code (z.B. EUR, USD, "
    "CHF, GBP). Erkennbar am Waehrungssymbol (€, $, CHF, £) oder Land. Ist die "
    "Waehrung nicht erkennbar, setze 'currency' auf 'EUR'.\n"
    "Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt mit exakt den Keys "
    "'title', 'amount', 'date', 'category', 'currency'."
)

ALLOWED_CATEGORIES = set(DEFAULT_CATEGORIES)
# Titel, falls das Modell kein Geschaeft lesen konnte (leerer String). Ohne ihn
# stuende die Ausgabe namenlos in der Liste.
FALLBACK_TITLE = "Kassenbon"


class ReceiptAnalysisError(Exception):
    """Ollama ist nicht erreichbar oder die Antwort ist nicht verwertbar.

    Die Nachricht ist bewusst nutzerverstaendlich (deutsch) formuliert — sie wird
    seit der Status-Rueckmeldung (Receipt-Jobs) im Frontend angezeigt.
    """


# ---------- Modell-Verwaltung (Auto-Pull) ----------

# Verhindert parallele Downloads, wenn z. B. der Start-Check und ein Scan
# gleichzeitig feststellen, dass das Modell fehlt.
_pull_lock = asyncio.Lock()


def _same_model(name: str, wanted: str) -> bool:
    """Vergleicht Modellnamen tolerant gegenueber dem impliziten ``:latest``-Tag."""

    def normalize(value: str) -> str:
        return value if ":" in value else f"{value}:latest"

    return normalize(name) == normalize(wanted)


async def is_model_available() -> bool:
    """Prueft ueber ``GET /api/tags``, ob das Vision-Modell lokal vorhanden ist.

    Wirft ``ReceiptAnalysisError``, wenn Ollama selbst nicht erreichbar ist.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
        response.raise_for_status()
        models = response.json().get("models", [])
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning(
            "Ollama nicht erreichbar beim Modell-Check (%s): %s",
            type(exc).__name__,
            exc,
        )
        raise ReceiptAnalysisError(
            f"KI-Dienst (Ollama) nicht erreichbar ({type(exc).__name__})"
        ) from exc
    return any(_same_model(m.get("name", ""), OLLAMA_MODEL) for m in models)


async def ensure_model() -> None:
    """Stellt sicher, dass ``OLLAMA_MODEL`` vorhanden ist — laedt es sonst herunter.

    Hintergrund (Bugfix 2026-09-25): Nach ``docker compose down -v`` (z. B. beim
    ``splitbill``→``yousplit``-Reset) ist auch das Volume ``ollama_models`` weg.
    Jeder Scan scheiterte danach mit ``404 model not found`` — still, nur im Log.
    Jetzt wird das Modell beim Backend-Start und notfalls vor einem Scan
    automatisch per ``POST /api/pull`` geholt.
    """
    if await is_model_available():
        return

    async with _pull_lock:
        # Double-Check: ein paralleler Aufrufer hat das Modell evtl. gerade geladen
        if await is_model_available():
            return

        logger.warning(
            "Modell '%s' fehlt in Ollama — starte Download (einmalig, ~3 GB, "
            "kann mehrere Minuten dauern) ...",
            OLLAMA_MODEL,
        )
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=OLLAMA_PULL_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{OLLAMA_URL}/api/pull",
                    json={"model": OLLAMA_MODEL, "stream": False},
                )
            response.raise_for_status()
            result = response.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Modell-Download fehlgeschlagen (HTTP %s): %s",
                exc.response.status_code,
                exc.response.text[:500],
            )
            raise ReceiptAnalysisError(
                "KI-Modell konnte nicht heruntergeladen werden "
                f"(HTTP {exc.response.status_code})"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            logger.error(
                "Modell-Download fehlgeschlagen (%s): %s", type(exc).__name__, exc
            )
            raise ReceiptAnalysisError(
                f"KI-Modell konnte nicht heruntergeladen werden ({type(exc).__name__})"
            ) from exc

        if isinstance(result, dict) and result.get("error"):
            logger.error("Modell-Download meldet Fehler: %s", result["error"])
            raise ReceiptAnalysisError(
                f"KI-Modell konnte nicht heruntergeladen werden: {result['error']}"
            )

        logger.info(
            "Modell '%s' heruntergeladen (%.0f s).",
            OLLAMA_MODEL,
            time.monotonic() - started,
        )


async def ensure_model_on_startup(attempts: int = 12, delay_seconds: float = 5) -> None:
    """Start-Check fuer den ``lifespan``: Modell pruefen/laden, ohne zu crashen.

    Ollama startet parallel zum Backend (``depends_on: service_started``) und ist
    in den ersten Sekunden evtl. noch nicht erreichbar — daher einige Versuche
    mit Pause. Scheitert alles, wird nur geloggt: der naechste Scan versucht es
    erneut (siehe ``analyze_receipt``).
    """
    for attempt in range(1, attempts + 1):
        try:
            await ensure_model()
        except ReceiptAnalysisError as exc:
            if attempt == attempts:
                logger.error(
                    "Modell-Check beim Start endgueltig fehlgeschlagen: %s", exc
                )
                return
            logger.info(
                "Modell-Check beim Start: Versuch %d/%d fehlgeschlagen, neuer "
                "Versuch in %.0f s",
                attempt,
                attempts,
                delay_seconds,
            )
            await asyncio.sleep(delay_seconds)
        else:
            logger.info("Modell-Check beim Start: '%s' ist bereit.", OLLAMA_MODEL)
            return


# ---------- Bild-Vorbereitung ----------

# Bild-Tokens und Rechenzeit wachsen mit der Pixelflaeche — fuer das LESEN
# eines Bons reicht ein Bruchteil der Aufloesung von Handy-Fotos/Screenshots
MAX_IMAGE_PIXELS = 1_800_000


def _prepare_image(image_bytes: bytes) -> bytes:
    """Dreht das Bild aufrecht, verkleinert zu grosse Bilder, normalisiert auf JPEG."""
    try:
        # Handy-Kameras speichern Hochkant-Fotos oft liegend und vermerken die
        # Drehung nur im EXIF-Tag. Das JPEG unten enthaelt kein EXIF mehr — ohne
        # exif_transpose bekaeme das Modell den Bon um 90° gedreht zu lesen.
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes)))
        image = image.convert("RGB")
    except Exception as exc:
        logger.warning("Bild nicht lesbar: %s", exc)
        raise ReceiptAnalysisError("Die Bilddatei konnte nicht gelesen werden") from exc

    pixels = image.width * image.height
    if pixels > MAX_IMAGE_PIXELS:
        scale = (MAX_IMAGE_PIXELS / pixels) ** 0.5
        new_size = (
            max(1, round(image.width * scale)),
            max(1, round(image.height * scale)),
        )
        image = image.resize(new_size, Image.LANCZOS)
        logger.info(
            "Bon-Bild verkleinert: %d px -> %dx%d", pixels, new_size[0], new_size[1]
        )

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


# ---------- Analyse ----------

def _is_model_missing(exc: httpx.HTTPStatusError) -> bool:
    """404 mit ``{"error": "model '...' not found"}`` = Modell nicht geladen."""
    return exc.response.status_code == 404 and "not found" in exc.response.text


async def _post_chat(payload: dict) -> httpx.Response:
    """Ein ``/api/chat``-Aufruf; HTTP-Fehler werden als ``HTTPStatusError`` geworfen."""
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
        response = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
    response.raise_for_status()
    return response


async def analyze_receipt(image_bytes: bytes) -> ReceiptAnalysis:
    """Schickt das Bon-Foto an Ollama und gibt die validierte Analyse zurück.

    Fehlt das Modell (404), wird es einmalig automatisch geladen und der Aufruf
    wiederholt (Selbstheilung statt stillem Scheitern).
    """
    image_b64 = base64.b64encode(_prepare_image(image_bytes)).decode("utf-8")

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "user", "content": RECEIPT_PROMPT, "images": [image_b64]}
        ],
        # Zwingt Ollama, syntaktisch valides JSON auszugeben
        "format": "json",
        "stream": False,
        # Denken nur bei Qwen3.x abschalten (reines Ablesen braucht es nicht und
        # es kostet auf CPU Minuten) — siehe ``thinking_options``.
        **thinking_options(OLLAMA_MODEL),
        "options": {
            # Bilder zaehlen als Tokens (proportional zur Pixelflaeche).
            # Hohe Bon-Screenshots sprengen Ollamas Default von 4096.
            "num_ctx": 16384,
            # Deterministische, faktentreue Extraktion — kein "kreatives"
            # Halluzinieren von Datum/Betrag. Fuer reines Ablesen ideal.
            "temperature": 0,
        },
    }

    started = time.monotonic()
    try:
        try:
            response = await _post_chat(payload)
        except httpx.HTTPStatusError as exc:
            if not _is_model_missing(exc):
                raise
            # Modell fehlt (z. B. nach Volume-Reset) → laden und einmal wiederholen
            logger.warning(
                "Ollama kennt Modell '%s' nicht — lade es nach und wiederhole den Scan.",
                OLLAMA_MODEL,
            )
            await ensure_model()
            started = time.monotonic()
            response = await _post_chat(payload)
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Ollama antwortete mit HTTP %s: %s",
            exc.response.status_code,
            exc.response.text[:1000],
        )
        raise ReceiptAnalysisError(
            f"KI-Dienst antwortete mit HTTP {exc.response.status_code}"
        ) from exc
    except httpx.TimeoutException as exc:
        logger.error(
            "Ollama-Timeout nach %.0f s (Limit %.0f s)",
            time.monotonic() - started,
            OLLAMA_TIMEOUT_SECONDS,
        )
        raise ReceiptAnalysisError(
            "Die KI hat zu lange gebraucht (Timeout). Bitte erneut versuchen."
        ) from exc
    except httpx.HTTPError as exc:
        # Der Typ verraet die Ursache: ConnectError, ReadError, ...
        logger.error("Ollama nicht erreichbar (%s): %s", type(exc).__name__, exc)
        raise ReceiptAnalysisError(
            f"KI-Dienst (Ollama) nicht erreichbar ({type(exc).__name__})"
        ) from exc

    logger.info("Ollama-Analyse fertig nach %.1f s", time.monotonic() - started)

    try:
        content: str = response.json()["message"]["content"]
    except (KeyError, ValueError) as exc:
        logger.error("Unerwartetes Antwortformat von Ollama: %s", response.text[:1000])
        raise ReceiptAnalysisError("Unerwartetes Antwortformat der KI") from exc

    logger.debug("Roher Modell-Text: %r", content)

    try:
        analysis = ReceiptAnalysis.model_validate_json(content)
    except ValidationError as exc:
        # Der rohe Modell-Text zeigt im Docker-Log, WAS das Modell
        # stattdessen geantwortet hat
        logger.error(
            "Modell-Antwort nicht verwertbar: %s | roher Text: %r", exc, content
        )
        raise ReceiptAnalysisError(
            "Die KI konnte den Bon nicht lesen (Antwort unbrauchbar)"
        ) from exc

    # Alte Namen umbenennen, halluzinierte Kategorien auf den Fallback mappen
    analysis.category = LEGACY_ALIASES.get(analysis.category, analysis.category)
    if analysis.category not in ALLOWED_CATEGORIES:
        logger.info(
            "Unbekannte Kategorie '%s' → '%s'", analysis.category, FALLBACK_CATEGORY
        )
        analysis.category = FALLBACK_CATEGORY

    # DB-Spalte ist String(200)
    analysis.title = analysis.title.strip()[:200] or FALLBACK_TITLE
    return analysis
