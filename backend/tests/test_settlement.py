"""Tests fuer Kassensturz (settlement.py) und faire Verteilung (splits.py).

Ausfuehren (im backend-Ordner):

    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from settlement import calculate_settlement, collect_persons  # noqa: E402
from splits import fair_split  # noqa: E402


@dataclass
class Exp:
    payer_name: str
    amount: float
    split_ratio: float = 0.5
    exchange_rate: float = 1.0
    splits: dict[str, float] | None = field(default=None)


def nets(result) -> dict[str, float]:
    return {b.name: b.net for b in result.balances}


class SettlementTest(unittest.TestCase):
    def test_ohne_ausgaben_ist_alles_leer(self) -> None:
        result = calculate_settlement([])
        self.assertEqual(result.balances, [])
        self.assertEqual(result.transactions, [])

    def test_mitglieder_ohne_ausgabe_zaehlen_mit(self) -> None:
        result = calculate_settlement([], ["Kev", "Anna"])
        self.assertEqual([b.name for b in result.balances], ["Kev", "Anna"])
        self.assertEqual(result.transactions, [])

    def test_zwei_personen_fuenfzig_fuenfzig(self) -> None:
        result = calculate_settlement([Exp("Kev", 100.0)], ["Kev", "Anna"])
        self.assertEqual(nets(result), {"Kev": 50.0, "Anna": -50.0})
        [transaction] = result.transactions
        self.assertEqual(
            (transaction.from_person, transaction.to_person, transaction.amount),
            ("Anna", "Kev", 50.0),
        )

    def test_einzige_person_traegt_alles_selbst(self) -> None:
        result = calculate_settlement([Exp("Kev", 30.0, split_ratio=0.2)])
        self.assertEqual(nets(result), {"Kev": 0.0})
        self.assertEqual(result.transactions, [])

    def test_split_ratio_verteilt_rest_auf_die_anderen(self) -> None:
        result = calculate_settlement(
            [Exp("Kev", 90.0, split_ratio=0.0)], ["Kev", "Anna", "Tom"]
        )
        self.assertEqual(nets(result), {"Kev": 90.0, "Anna": -45.0, "Tom": -45.0})

    def test_splits_haben_vorrang_vor_split_ratio(self) -> None:
        expense = Exp("Kev", 100.0, split_ratio=0.5, splits={"Kev": 0.0, "Anna": 100.0})
        result = calculate_settlement([expense], ["Kev", "Anna"])
        self.assertEqual(nets(result), {"Kev": 100.0, "Anna": -100.0})

    def test_mitesser_ohne_eigene_ausgabe_taucht_auf(self) -> None:
        expense = Exp("Kev", 30.0, splits={"Kev": 10.0, "Tom": 20.0})
        self.assertEqual(collect_persons([expense]), ["Kev", "Tom"])
        result = calculate_settlement([expense])
        self.assertEqual(nets(result), {"Kev": 20.0, "Tom": -20.0})

    def test_fremdwaehrung_wird_in_eur_umgerechnet(self) -> None:
        expense = Exp("Kev", 100.0, exchange_rate=0.9, splits={"Kev": 50.0, "Anna": 50.0})
        result = calculate_settlement([expense])
        self.assertEqual(nets(result), {"Kev": 45.0, "Anna": -45.0})
        self.assertEqual(result.transactions[0].amount, 45.0)

    def test_gegenlaeufige_ausgaben_gleichen_sich_aus(self) -> None:
        expenses = [Exp("Kev", 40.0), Exp("Anna", 40.0)]
        result = calculate_settlement(expenses, ["Kev", "Anna"])
        self.assertEqual(nets(result), {"Kev": 0.0, "Anna": 0.0})
        self.assertEqual(result.transactions, [])

    def test_ausgleich_braucht_hoechstens_n_minus_1_ueberweisungen(self) -> None:
        expenses = [
            Exp("A", 100.0, splits={"A": 25.0, "B": 25.0, "C": 25.0, "D": 25.0}),
            Exp("B", 60.0, splits={"A": 15.0, "B": 15.0, "C": 15.0, "D": 15.0}),
        ]
        result = calculate_settlement(expenses)
        self.assertLessEqual(len(result.transactions), 3)
        # Wer zahlt, was er schuldet: die Salden gehen nach den Ueberweisungen auf 0
        saldo = nets(result)
        for t in result.transactions:
            saldo[t.from_person] += t.amount
            saldo[t.to_person] -= t.amount
        for value in saldo.values():
            self.assertAlmostEqual(value, 0.0, places=2)

    def test_summe_der_salden_ist_null(self) -> None:
        expenses = [
            Exp("Kev", 33.33, split_ratio=0.3),
            Exp("Anna", 12.5, splits={"Kev": 2.5, "Anna": 5.0, "Tom": 5.0}),
        ]
        result = calculate_settlement(expenses, ["Kev", "Anna", "Tom"])
        self.assertAlmostEqual(sum(nets(result).values()), 0.0, places=1)


class FairSplitTest(unittest.TestCase):
    def test_leere_personenliste(self) -> None:
        self.assertEqual(fair_split(10.0, []), {})

    def test_summe_entspricht_exakt_dem_betrag(self) -> None:
        for amount, count in [(10.0, 3), (0.01, 4), (100.0, 7), (33.33, 3)]:
            with self.subTest(amount=amount, count=count):
                names = [f"P{i}" for i in range(count)]
                splits = fair_split(amount, names)
                self.assertEqual(round(sum(splits.values()) * 100), round(amount * 100))

    def test_rundungsrest_geht_an_die_erste_person(self) -> None:
        self.assertEqual(
            fair_split(10.0, ["A", "B", "C"]), {"A": 3.34, "B": 3.33, "C": 3.33}
        )


if __name__ == "__main__":
    unittest.main()
