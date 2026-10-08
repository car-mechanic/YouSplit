"""Tests fuer die Upload-Grenzen (Bon-Bild und Kontoauszug-PDF) ueber HTTP.

Ausfuehren (im backend-Ordner; braucht fastapi + sqlalchemy + httpx, nutzt SQLite):

    python -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest
import uuid

_DB_DIR = tempfile.mkdtemp(prefix="yousplit-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_DIR}/test.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import models  # noqa: E402
from database import Base, SessionLocal, engine  # noqa: E402
from routers import lists  # noqa: E402

# Kleine Grenze fuer die Tests, damit keine 20-MB-Koerper gebaut werden muessen
TEST_LIMIT = 1024


class UploadLimitTest(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            shared = models.SharedList(title="Test")
            db.add(shared)
            db.commit()
            self.list_id = shared.id

        self._orig = (
            lists.MAX_RECEIPT_BYTES,
            lists.MAX_STATEMENT_BYTES,
            lists._process_receipt_in_background,
        )
        self.processed: list[bytes] = []

        async def fake_process(
            job_id: uuid.UUID, list_id: uuid.UUID, payer_name: str, image: bytes
        ) -> None:
            self.processed.append(image)

        lists.MAX_RECEIPT_BYTES = TEST_LIMIT
        lists.MAX_STATEMENT_BYTES = TEST_LIMIT
        lists._process_receipt_in_background = fake_process

        app = FastAPI()
        app.include_router(lists.router, prefix="/api")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        (
            lists.MAX_RECEIPT_BYTES,
            lists.MAX_STATEMENT_BYTES,
            lists._process_receipt_in_background,
        ) = self._orig

    def upload_receipt(self, data: bytes, content_type: str = "image/jpeg"):
        return self.client.post(
            f"/api/lists/{self.list_id}/receipts",
            data={"payer_name": "Kev"},
            files={"receipt": ("bon.jpg", data, content_type)},
        )

    def job_count(self) -> int:
        with SessionLocal() as db:
            return db.query(models.ReceiptJob).count()

    def test_bon_an_der_grenze_wird_angenommen(self) -> None:
        image = b"x" * TEST_LIMIT
        response = self.upload_receipt(image)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(self.processed, [image])
        self.assertEqual(self.job_count(), 1)

    def test_zu_grosser_bon_wird_abgelehnt_und_legt_keinen_job_an(self) -> None:
        response = self.upload_receipt(b"x" * (TEST_LIMIT + 1))
        self.assertEqual(response.status_code, 413)
        self.assertIn("Das Bild ist zu groß", response.json()["detail"])
        self.assertEqual(self.processed, [])
        self.assertEqual(self.job_count(), 0)

    def test_bon_muss_ein_bild_sein(self) -> None:
        response = self.upload_receipt(b"%PDF-1.7", content_type="application/pdf")
        self.assertEqual(response.status_code, 400)

    def test_zu_grosser_kontoauszug_wird_abgelehnt(self) -> None:
        response = self.client.post(
            f"/api/lists/{self.list_id}/bank-statement/parse",
            files={"statement": ("auszug.pdf", b"%PDF" + b"x" * TEST_LIMIT)},
        )
        self.assertEqual(response.status_code, 413)
        self.assertIn("Das PDF ist zu groß", response.json()["detail"])

    def test_kontoauszug_muss_ein_pdf_sein(self) -> None:
        response = self.client.post(
            f"/api/lists/{self.list_id}/bank-statement/parse",
            files={"statement": ("auszug.pdf", b"kein pdf")},
        )
        self.assertEqual(response.status_code, 400)

    def test_defektes_pdf_ergibt_422_mit_ursache(self) -> None:
        response = self.client.post(
            f"/api/lists/{self.list_id}/bank-statement/parse",
            files={"statement": ("auszug.pdf", b"%PDF-1.7 kaputt")},
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("konnte nicht gelesen werden", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
