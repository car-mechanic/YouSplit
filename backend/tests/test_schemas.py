"""Tests fuer die Eingabe-Validierung der Schemas (API-Grenze).

Ausfuehren (im backend-Ordner; braucht nur pydantic):

    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import ValidationError  # noqa: E402

import schemas  # noqa: E402


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
