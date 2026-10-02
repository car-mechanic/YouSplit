"""Faire Gleichverteilung eines Betrags auf mehrere Personen (Roadmap 4.0 #2).

Reine, testbare Logik ohne DB-/HTTP-Bezug. Spiegelt die Konvention des
Frontend-``splitMath.ts``: der Betrag wird moeglichst gleichmaessig auf Cent
gerundet verteilt, der Rundungsrest ("1-Cent-Problem") geht an die **erste**
Person, sodass die Summe der Anteile **exakt** dem Betrag entspricht.
"""


def fair_split(amount: float, persons: list[str]) -> dict[str, float]:
    """Verteilt ``amount`` gleichmaessig auf ``persons`` (Summe = amount exakt).

    Rechnet bewusst in ganzen Cent, um Fliesskomma-Drift zu vermeiden; der
    Rundungsrest wird der ersten Person zugeschlagen. Bei leerer Personenliste
    ein leeres Dict. Doppelte Namen sind nicht vorgesehen (die Aufrufer liefern
    eine deduplizierte Liste).
    """
    count = len(persons)
    if count == 0:
        return {}

    total_cents = round(amount * 100)
    base = total_cents // count
    remainder = total_cents - base * count  # 0..count-1 zusaetzliche Cent

    splits = {name: base / 100 for name in persons}
    # Rundungsrest der ersten Person zuschlagen (Konvention wie im Frontend).
    splits[persons[0]] = (base + remainder) / 100
    return splits
