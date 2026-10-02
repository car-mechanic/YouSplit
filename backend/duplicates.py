"""Duplikats-Erkennung fuer gescannte Bons (reine Logik, ohne DB).

Ein gescannter Bon gilt als Duplikat, wenn in der Liste schon eine Ausgabe mit
**gleichem Geschaeft, gleichem Betrag und gleichem Datum** existiert. Betrag und
Datum vergleicht der Router exakt (Betrag auf Cent gerundet); hier steckt nur der
unscharfe Geschaeftsvergleich. Er muss unscharf sein, weil das Vision-Modell
denselben Bon bei zwei Scans leicht unterschiedlich benennen kann
("REWE" vs. "Rewe Markt GmbH").
"""

import re
from difflib import SequenceMatcher

# Ab diesem Aehnlichkeitswert (0..1) gelten zwei Geschaeftsnamen als gleich.
MIN_SIMILARITY = 0.75
# Mindestlaenge fuer den Teilstring-Treffer ("rewe" in "rewecenter"), damit
# kurze Fragmente wie "an" nicht jeden Namen treffen.
MIN_CONTAINED_LENGTH = 3

_NON_ALNUM = re.compile(r"[^0-9a-zäöüß]+")
# Rechtsform-/Fuellwoerter, die zwischen zwei Scans desselben Bons schwanken.
_NOISE_WORDS = frozenset(
    {"gmbh", "ag", "kg", "ohg", "co", "markt", "filiale", "fil", "shop", "store"}
)


def normalize_shop(name: str) -> str:
    """Kleinschreibung, ohne Satzzeichen/Leerraum und ohne Rechtsform-Zusaetze."""
    tokens = [
        token
        for token in _NON_ALNUM.split(name.casefold())
        if token and token not in _NOISE_WORDS
    ]
    # Besteht der Name NUR aus Fuellwoertern ("Markt"), lieber roh vergleichen
    return "".join(tokens) or _NON_ALNUM.sub("", name.casefold())


def shops_match(first: str, second: str) -> bool:
    """True, wenn beide Geschaeftsnamen sehr wahrscheinlich dasselbe Geschaeft meinen."""
    a, b = normalize_shop(first), normalize_shop(second)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = sorted((a, b), key=len)
    if len(shorter) >= MIN_CONTAINED_LENGTH and shorter in longer:
        return True
    return SequenceMatcher(None, a, b).ratio() >= MIN_SIMILARITY
