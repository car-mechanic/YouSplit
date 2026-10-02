"""Wechselkurs-Abfrage (Roadmap 2.0 #3, Multi-Currency).

Kapselt den Zugriff auf die freie, Key-lose **Frankfurter-API**
(https://www.frankfurter.app) — analog zu ``ollama_client.py`` spricht kein
anderer Code direkt mit diesem externen Dienst.

Kurs-Konvention (projektweit): ``exchange_rate`` ist der **EUR-Wert einer
Einheit der Fremdwährung**. Der EUR-Betrag einer Ausgabe ist damit stets
``amount * exchange_rate`` (siehe settlement.py und das Frontend). Das entspricht
direkt der Frankfurter-Antwort für ``from={WÄHRUNG}&to=EUR`` (Feld ``rates.EUR``).
"""

import logging
import os

import httpx

logger = logging.getLogger("yousplit.currency")

FRANKFURTER_URL = os.getenv("FRANKFURTER_URL", "https://api.frankfurter.app/latest")

# Basiswährung, in der Kassensturz & Statistiken rechnen.
BASE_CURRENCY = "EUR"

# Vom Frontend angebotene Währungen. Aufgeteilt in Haupt- und "Mehr…"-Block
# (Roadmap 3.0 #2), damit das Frontend-Dropdown die kuratierten Hauptwährungen
# zeigt und die europäischen Nebenwährungen erst auf Wunsch aufklappt. Alle hier
# gelisteten Codes werden von der Frankfurter-API unterstützt (sonst gäbe es
# keinen Kurs).
MAIN_CURRENCIES = ("EUR", "USD", "CHF", "GBP")
# Weitere europäische Währungen (Frankfurter-kompatibel): Skandinavien, Mittel-
# und Osteuropa sowie Island.
MORE_CURRENCIES = ("SEK", "NOK", "DKK", "PLN", "CZK", "HUF", "RON", "BGN", "ISK")
SUPPORTED_CURRENCIES = MAIN_CURRENCIES + MORE_CURRENCIES

# Kurs-API antwortet üblicherweise in <1 s — kein minutenlanges Warten wie bei
# der lokalen Vision-Inferenz nötig.
FRANKFURTER_TIMEOUT_SECONDS = float(os.getenv("EXCHANGE_RATE_TIMEOUT_SECONDS", "10"))


class ExchangeRateError(Exception):
    """Die Kurs-API ist nicht erreichbar oder liefert keinen verwertbaren Kurs."""


async def get_exchange_rate(currency: str) -> float:
    """Liefert den Tageskurs: wie viele **EUR** ist 1 Einheit von ``currency`` wert.

    - ``EUR`` → ``1.0`` (kein API-Aufruf nötig).
    - Sonst: Frankfurter-Abruf ``from={currency}&to=EUR`` und Rückgabe von
      ``rates.EUR``.

    Wirft ``ExchangeRateError`` bei Netz-/Format-Problemen — der aufrufende
    Endpoint übersetzt das in einen klaren HTTP-Fehler, statt still einen
    falschen Kurs (z. B. 1.0) zu speichern und damit die EUR-Salden zu verfälschen.
    """
    code = currency.strip().upper()
    if code == BASE_CURRENCY:
        return 1.0

    try:
        # follow_redirects: api.frankfurter.app antwortet mit 301 auf die neue
        # Domain (api.frankfurter.dev) und behaelt dabei die Query-Parameter —
        # ohne Folgen des Redirects kaeme nur HTML statt JSON zurueck.
        async with httpx.AsyncClient(
            timeout=FRANKFURTER_TIMEOUT_SECONDS, follow_redirects=True
        ) as client:
            response = await client.get(
                FRANKFURTER_URL, params={"from": code, "to": BASE_CURRENCY}
            )
        response.raise_for_status()
        data = response.json()
        rate = data["rates"][BASE_CURRENCY]
    except httpx.HTTPError as exc:
        logger.error("Kursabruf fuer %s fehlgeschlagen (%s): %s", code, type(exc).__name__, exc)
        raise ExchangeRateError(
            f"Wechselkurs für {code} nicht abrufbar ({type(exc).__name__})"
        ) from exc
    except (KeyError, ValueError) as exc:
        # Unbekannte Währung liefert z. B. {"rates": {}} ohne EUR-Schlüssel
        logger.error("Unerwartete Kurs-Antwort fuer %s: %s", code, exc)
        raise ExchangeRateError(
            f"Kein EUR-Kurs für Währung '{code}' erhalten"
        ) from exc

    return float(rate)
