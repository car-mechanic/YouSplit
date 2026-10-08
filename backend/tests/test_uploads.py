"""Tests fuer die Upload-Grenzen (Kontoauszug-PDF) ueber HTTP.

Ausfuehren (im backend-Ordner; braucht fastapi + sqlalchemy + httpx, nutzt SQLite):

    python -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest

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

        self._orig_limit = lists.MAX_STATEMENT_BYTES
        lists.MAX_STATEMENT_BYTES = TEST_LIMIT

        app = FastAPI()
        app.include_router(lists.router, prefix="/api")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        lists.MAX_STATEMENT_BYTES = self._orig_limit

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
