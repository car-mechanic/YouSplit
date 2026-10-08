"""Tests fuer die Duplikats-Erkennung (Geschaeftsvergleich + Suche in der Liste).

Ausfuehren (im backend-Ordner; braucht fastapi + sqlalchemy, nutzt SQLite):

    python -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest
from datetime import date

# Vor dem Import von ``database``: SQLite statt Postgres (Datei, weil jede
# Verbindung einer In-Memory-DB ihre eigene, leere DB waere).
_DB_DIR = tempfile.mkdtemp(prefix="yousplit-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_DIR}/test.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duplicates  # noqa: E402
import models  # noqa: E402
from database import Base, SessionLocal, engine  # noqa: E402
from routers import lists  # noqa: E402


class ShopsMatchTest(unittest.TestCase):
    def test_gleiche_namen_trotz_schreibweise(self) -> None:
        self.assertTrue(duplicates.shops_match("REWE", "Rewe"))
        self.assertTrue(duplicates.shops_match("Rewe Markt GmbH", "REWE"))
        self.assertTrue(duplicates.shops_match("Dm-Drogerie Markt", "dm drogerie"))

    def test_teilstring_und_kleine_abweichung(self) -> None:
        self.assertTrue(duplicates.shops_match("REWE", "Rewe Center Köln"))
        self.assertTrue(duplicates.shops_match("Edeka", "Edaka"))

    def test_verschiedene_geschaefte(self) -> None:
        self.assertFalse(duplicates.shops_match("REWE", "Aldi"))
        self.assertFalse(duplicates.shops_match("Aldi Süd", "Aldi Nord"))
        self.assertFalse(duplicates.shops_match("Lidl", "Edeka"))

    def test_leere_oder_nur_fuellwoerter(self) -> None:
        self.assertFalse(duplicates.shops_match("", "REWE"))
        self.assertFalse(duplicates.shops_match("---", "REWE"))
        # Nur Fuellwort: faellt auf den Rohvergleich zurueck, statt leer zu matchen
        self.assertTrue(duplicates.shops_match("Markt", "markt"))
        self.assertFalse(duplicates.shops_match("Markt", "Shop"))


class DbTestCase(unittest.TestCase):
    """Frische SQLite-DB mit einer Liste je Test."""

    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        self.db = SessionLocal()
        shared = models.SharedList(title="Test")
        self.db.add(shared)
        self.db.commit()
        self.list_id = shared.id

    def tearDown(self) -> None:
        self.db.close()

    def add_expense(
        self, title: str, amount: float, receipt_date: date | None
    ) -> models.Expense:
        expense = models.Expense(
            list_id=self.list_id,
            title=title,
            amount=amount,
            payer_name="Kev",
            receipt_date=receipt_date,
        )
        self.db.add(expense)
        self.db.commit()
        return expense

    def expense_count(self) -> int:
        self.db.expire_all()
        return self.db.query(models.Expense).count()


class FindDuplicateTest(DbTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.add_expense("REWE", 24.50, date(2026, 8, 12))

    def find(self, **overrides: object) -> models.Expense | None:
        args: dict = dict(amount=24.50, on_date=date(2026, 8, 12), title="REWE")
        args.update(overrides)
        return lists._find_duplicate(self.db, self.list_id, **args)

    def test_gleiches_geschaeft_betrag_datum(self) -> None:
        self.assertIsNotNone(self.find())
        self.assertIsNotNone(self.find(title="Rewe Markt GmbH"))

    def test_betrag_wird_auf_cent_gerundet_verglichen(self) -> None:
        self.assertIsNotNone(self.find(amount=24.499999))

    def test_anderes_geschaeft_betrag_oder_datum_ist_kein_duplikat(self) -> None:
        self.assertIsNone(self.find(title="Aldi"))
        self.assertIsNone(self.find(amount=24.60))
        self.assertIsNone(self.find(on_date=date(2026, 8, 13)))

    def test_ohne_titel_zaehlen_nur_betrag_und_datum(self) -> None:
        # manuelle Eingabe: Verhalten unveraendert
        self.assertIsNotNone(self.find(title=None))
        self.assertIsNotNone(
            lists._find_duplicate(
                self.db, self.list_id, 24.50, date(2026, 8, 12)
            )
        )


if __name__ == "__main__":
    unittest.main()
