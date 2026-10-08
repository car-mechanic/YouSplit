"""Tests fuer die Eingabe-Validierung der Schemas (API-Grenze + KI-Antwort).

Ausfuehren (im backend-Ordner; braucht nur pydantic):

    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import ValidationError  # noqa: E402

import schemas  # noqa: E402


def _analysis(amount: object) -> schemas.ReceiptAnalysis:
    return schemas.ReceiptAnalysis.model_validate(
        {"title": "REWE", "amount": amount, "date": None, "category": "Lebensmittel"}
    )


class ReceiptAmountTest(unittest.TestCase):
    def test_betrags_texte_der_ki_werden_gelesen(self) -> None:
        cases = {
            "24,50": 24.50,
            "24,50 €": 24.50,
            "EUR 24.50": 24.50,
            "CHF 12.50": 12.50,
            "$7.99": 7.99,
            "1.234,56": 1234.56,
            "1.234,56 €": 1234.56,
            "1,234.56": 1234.56,
            "137.77": 137.77,
            "12,50.": 12.50,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertAlmostEqual(_analysis(raw).amount, expected)

    def test_zahlen_bleiben_unveraendert(self) -> None:
        self.assertEqual(_analysis(137.77).amount, 137.77)

    def test_unbrauchbare_betraege_werden_abgelehnt(self) -> None:
        for raw in ("", "kein Betrag", "-5,00", "0", float("inf"), float("nan")):
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                _analysis(raw)


def _expense(**overrides: object) -> dict:
    data: dict = {"title": "Pizza", "amount": 20.0, "payer_name": "Kev"}
    data.update(overrides)
    return data


class ExpenseValidationTest(unittest.TestCase):
    def test_gueltige_ausgabe(self) -> None:
        expense = schemas.ExpenseCreate.model_validate(
            _expense(splits={"Kev": 10.0, "Anna": 10.0})
        )
        self.assertEqual(expense.category, "Unknown/Manuell")
        self.assertEqual(expense.splits, {"Kev": 10.0, "Anna": 10.0})

    def test_unendliche_und_nan_betraege_werden_abgelehnt(self) -> None:
        for model in (schemas.ExpenseCreate, schemas.ExpenseUpdate):
            for amount in (float("inf"), float("nan")):
                with self.subTest(model=model.__name__, amount=amount):
                    with self.assertRaises(ValidationError):
                        model.model_validate(
                            _expense(amount=amount, category="Sonstiges")
                        )
        with self.assertRaises(ValidationError):
            schemas.BankImportItem.model_validate(
                {"title": "REWE", "amount": float("inf")}
            )

    def test_nan_in_der_aufteilung_wird_abgelehnt(self) -> None:
        # nan < 0 ist False und die Summenpruefung mit NaN ebenfalls: ohne eigene
        # Pruefung kaeme der Wert bis in den Kassensturz.
        for share in (float("nan"), float("inf"), -1.0):
            with self.subTest(share=share), self.assertRaises(ValidationError):
                schemas.ExpenseCreate.model_validate(
                    _expense(splits={"Kev": share, "Anna": 10.0})
                )

    def test_kategorie_passt_in_die_db_spalte(self) -> None:
        # Spalte ist String(100): laengere Werte liefen in Postgres auf einen 500er
        with self.assertRaises(ValidationError):
            schemas.ExpenseCreate.model_validate(_expense(category="x" * 101))
        with self.assertRaises(ValidationError):
            schemas.ExpenseCreate.model_validate(_expense(category=""))


if __name__ == "__main__":
    unittest.main()
