"""Kassensturz für N Personen — reine Berechnungslogik.

Bewusst ohne DB- oder FastAPI-Abhaengigkeit (nur die Pydantic-Antwort-Schemas),
damit die Logik testbar bleibt und fuer spaetere Clients wiederverwendbar ist
(siehe AI_CONTEXT.md, Abschnitt 2.5).

Aufteilungs-Konvention:
- **Advanced Split (Roadmap 3.0 #3):** Traegt eine Ausgabe eine explizite
  Pro-Person-Aufteilung ``splits`` ({Name: Betrag}), gilt genau diese — jede
  Person verbraucht ihren hinterlegten Betrag (der Zahler evtl. 0). Betraege
  stehen in der Erfassungswaehrung und werden ueber ``exchange_rate`` in EUR
  umgerechnet.
- **Fallback ``split_ratio``:** Ohne ``splits`` (Altdaten, gescannte Bons) traegt
  der Zahler ``split_ratio`` selbst; der Rest ``(1 - split_ratio)`` wird zu
  gleichen Teilen auf die **anderen** Personen verteilt. Fuer genau 2 Personen
  ergibt das exakt das alte 2-Personen-Verhalten. Ist der Zahler die einzige
  Person, traegt er alles selbst.
"""

from typing import Protocol

from schemas import PersonBalance, SettlementResponse, SettlementTransaction

# Betraege unterhalb eines halben Cents gelten als 0 (Fliesskomma-Rundung).
EPS = 0.005


class ExpenseLike(Protocol):
    """Minimaler Vertrag einer Ausgabe — erfuellt von ``models.Expense``."""

    payer_name: str
    amount: float
    split_ratio: float
    # Multi-Currency (Roadmap 2.0 #3): EUR-Wert einer Einheit der Erfassungs-
    # waehrung. Der Kassensturz rechnet ausschliesslich in EUR (Basiswaehrung).
    exchange_rate: float
    # Advanced Split (Roadmap 3.0 #3): explizite Pro-Person-Aufteilung oder None.
    splits: dict[str, float] | None


def collect_persons(expenses: list[ExpenseLike]) -> list[str]:
    """Alle beteiligten Personen in Reihenfolge ihres ersten Auftretens.

    Beruecksichtigt Zahler UND — dank Advanced Split — Personen, die zwar an
    einer Ausgabe beteiligt sind (in ``splits``), aber selbst nie gezahlt haben.
    So taucht ein reiner Mit-Esser im Kassensturz auf, sofern ihm eine Ausgabe
    einen Anteil zuweist.
    """
    persons: list[str] = []
    for expense in expenses:
        if expense.payer_name not in persons:
            persons.append(expense.payer_name)
        if expense.splits:
            for name in expense.splits:
                if name not in persons:
                    persons.append(name)
    return persons


def _net_balances(expenses: list[ExpenseLike]) -> dict[str, tuple[float, float]]:
    """Berechnet je Person ``(gezahlt, verbraucht)`` — in EUR."""
    persons = collect_persons(expenses)

    paid: dict[str, float] = {name: 0.0 for name in persons}
    share: dict[str, float] = {name: 0.0 for name in persons}

    for expense in expenses:
        payer = expense.payer_name
        rate = expense.exchange_rate
        # In EUR umrechnen: alle Salden entstehen in der Basiswaehrung
        amount = expense.amount * rate

        # Der Zahler hat stets den vollen Betrag ausgelegt.
        paid[payer] += amount

        if expense.splits:
            # Advanced Split: jede Person verbraucht exakt ihren hinterlegten
            # Anteil (ebenfalls in EUR umgerechnet).
            for name, part in expense.splits.items():
                share[name] += part * rate
            continue

        # Fallback ohne explizite Aufteilung: split_ratio-Logik.
        ratio = expense.split_ratio
        share[payer] += ratio * amount
        others = [name for name in persons if name != payer]
        remainder = (1 - ratio) * amount
        if others:
            per_head = remainder / len(others)
            for name in others:
                share[name] += per_head
        else:
            # Einzige Person in der Liste: sie traegt auch den Rest selbst
            share[payer] += remainder

    return {name: (paid[name], share[name]) for name in persons}


def _simplify_debts(net: dict[str, float]) -> list[SettlementTransaction]:
    """Minimiert die Anzahl Ueberweisungen (Greedy).

    Groesster Schuldner zahlt an groessten Glaeubiger, bis alle Salden bei 0
    liegen. Das erzeugt hoechstens ``n-1`` Transaktionen — die gaengige,
    praxistaugliche Loesung des Schuldenausgleichs.
    """
    # [name, offener Betrag] — Glaeubiger positiv, Schuldner als Betrag > 0
    creditors = sorted(
        ([name, value] for name, value in net.items() if value > EPS),
        key=lambda item: item[1],
        reverse=True,
    )
    debtors = sorted(
        ([name, -value] for name, value in net.items() if value < -EPS),
        key=lambda item: item[1],
        reverse=True,
    )

    transactions: list[SettlementTransaction] = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        debtor = debtors[i]
        creditor = creditors[j]
        payment = min(debtor[1], creditor[1])

        rounded = round(payment, 2)
        if rounded >= EPS:
            transactions.append(
                SettlementTransaction(
                    from_person=debtor[0],
                    to_person=creditor[0],
                    amount=rounded,
                )
            )

        debtor[1] -= payment
        creditor[1] -= payment
        if debtor[1] <= EPS:
            i += 1
        if creditor[1] <= EPS:
            j += 1

    return transactions


def calculate_settlement(expenses: list[ExpenseLike]) -> SettlementResponse:
    """Kompletter Kassensturz: Salden je Person + minimale Ausgleichszahlungen."""
    balances_raw = _net_balances(expenses)

    net = {name: paid - share for name, (paid, share) in balances_raw.items()}

    balances = [
        PersonBalance(
            name=name,
            paid=round(paid, 2),
            share=round(share, 2),
            net=round(paid - share, 2),
        )
        for name, (paid, share) in balances_raw.items()
    ]

    return SettlementResponse(
        balances=balances,
        transactions=_simplify_debts(net),
    )
