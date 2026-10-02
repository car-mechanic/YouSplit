"""Tests fuer die Duplikats-Erkennung beim Bon-Scan.

Ausfuehren (im backend-Ordner; braucht fastapi + sqlalchemy, nutzt SQLite):

    python -m unittest discover -s tests -v
"""

import asyncio
import os
import sys
import tempfile
import unittest
import uuid
from datetime import date

# Vor dem Import von ``database``: SQLite statt Postgres (Datei, weil jede
# Verbindung einer In-Memory-DB ihre eigene, leere DB waere).
_DB_DIR = tempfile.mkdtemp(prefix="yousplit-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_DIR}/test.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException  # noqa: E402

import duplicates  # noqa: E402
import models  # noqa: E402
import receipt_jobs  # noqa: E402
import schemas  # noqa: E402
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


def _analysis(title: str = "REWE", amount: float = 24.50) -> schemas.ReceiptAnalysis:
    return schemas.ReceiptAnalysis(
        title=title,
        amount=amount,
        date="2026-08-12",
        category="Lebensmittel",
        currency="EUR",
    )


class ScanFlowTest(DbTestCase):
    """Bon zweimal scannen: erst anlegen, dann als Duplikat melden."""

    def setUp(self) -> None:
        super().setUp()
        self.analysis = _analysis()
        # KI, Modell-Check und Kurs-API ersetzen (kein Ollama/Netz im Test)
        self._orig = (
            lists.analyze_receipt,
            lists.is_model_available,
            lists.get_exchange_rate,
        )

        async def fake_analyze(_: bytes) -> schemas.ReceiptAnalysis:
            return self.analysis

        async def fake_available() -> bool:
            return True

        async def fake_rate(_: str) -> float:
            return 1.0

        lists.analyze_receipt = fake_analyze
        lists.is_model_available = fake_available
        lists.get_exchange_rate = fake_rate

    def tearDown(self) -> None:
        (
            lists.analyze_receipt,
            lists.is_model_available,
            lists.get_exchange_rate,
        ) = self._orig
        super().tearDown()

    def scan(self) -> models.ReceiptJob:
        job = models.ReceiptJob(
            list_id=self.list_id,
            payer_name="Kev",
            status=receipt_jobs.STATUS_PROCESSING,
        )
        self.db.add(job)
        self.db.commit()
        asyncio.run(
            lists._process_receipt_in_background(
                job.id, self.list_id, "Kev", b"bild"
            )
        )
        self.db.expire_all()
        return self.db.get(models.ReceiptJob, job.id)

    def test_zweiter_scan_desselben_bons_wird_nicht_angelegt(self) -> None:
        first = self.scan()
        self.assertEqual(first.status, receipt_jobs.STATUS_DONE)
        self.assertEqual(self.expense_count(), 1)

        second = self.scan()
        self.assertEqual(second.status, receipt_jobs.STATUS_DUPLICATE)
        self.assertIn("bereits in der Liste", second.detail)
        self.assertIn("REWE", second.detail)
        self.assertEqual(second.result["amount"], 24.50)
        self.assertEqual(self.expense_count(), 1)  # nichts Neues angelegt

    def test_leicht_anderer_name_beim_zweiten_scan_wird_trotzdem_erkannt(self) -> None:
        self.scan()
        self.analysis = _analysis(title="Rewe Markt GmbH")
        self.assertEqual(self.scan().status, receipt_jobs.STATUS_DUPLICATE)

    def test_anderes_geschaeft_gleicher_betrag_ist_kein_duplikat(self) -> None:
        self.scan()
        self.analysis = _analysis(title="Aldi")
        self.assertEqual(self.scan().status, receipt_jobs.STATUS_DONE)
        self.assertEqual(self.expense_count(), 2)

    def test_trotzdem_hinzufuegen_legt_an_und_quittiert_den_job(self) -> None:
        self.scan()
        duplicate_job = self.scan()

        expense = asyncio.run(
            lists.confirm_duplicate_receipt(
                self.list_id, duplicate_job.id, db=self.db
            )
        )
        self.assertEqual(expense.title, "REWE")
        self.assertEqual(expense.receipt_date, date(2026, 8, 12))
        self.assertEqual(expense.payer_name, "Kev")
        self.assertEqual(self.expense_count(), 2)
        self.db.expire_all()
        self.assertIsNone(self.db.get(models.ReceiptJob, duplicate_job.id))

    def test_confirm_lehnt_nicht_wartende_jobs_ab(self) -> None:
        done_job = self.scan()
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                lists.confirm_duplicate_receipt(self.list_id, done_job.id, db=self.db)
            )
        self.assertEqual(ctx.exception.status_code, 409)

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                lists.confirm_duplicate_receipt(self.list_id, uuid.uuid4(), db=self.db)
            )
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
