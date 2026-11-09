"""Tests for renaming and deleting a list (menu on the overview cards).

Run (in the backend folder; uses SQLite):

    python -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timezone

_DB_DIR = tempfile.mkdtemp(prefix="yousplit-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_DIR}/test.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import models  # noqa: E402
from database import Base, SessionLocal, engine  # noqa: E402
from routers import lists  # noqa: E402


class ListManageApiTest(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        app = FastAPI()
        app.include_router(lists.router, prefix="/api")
        self.client = TestClient(app)
        self.list_id = self.client.post("/api/lists", json={"title": "WG"}).json()["id"]

    def test_rename_trims_and_stores_title(self) -> None:
        response = self.client.patch(
            f"/api/lists/{self.list_id}", json={"title": "  Urlaub  "}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Urlaub")
        stored = self.client.get(f"/api/lists/{self.list_id}").json()["title"]
        self.assertEqual(stored, "Urlaub")

    def test_rename_rejects_empty_title_and_unknown_list(self) -> None:
        empty = self.client.patch(f"/api/lists/{self.list_id}", json={"title": "  "})
        self.assertEqual(empty.status_code, 422)
        unknown = self.client.patch(f"/api/lists/{uuid.uuid4()}", json={"title": "X"})
        self.assertEqual(unknown.status_code, 404)

    def test_delete_removes_list_expenses_and_bookmarks(self) -> None:
        self.client.post(
            f"/api/lists/{self.list_id}/expenses",
            json={"title": "Pizza", "amount": 20, "payer_name": "Kev"},
        )
        with SessionLocal() as db:
            db.add(
                models.ListBookmark(
                    user_id="u1",
                    list_id=uuid.UUID(self.list_id),
                    last_visit=datetime.now(timezone.utc),
                )
            )
            db.commit()

        response = self.client.delete(f"/api/lists/{self.list_id}")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get(f"/api/lists/{self.list_id}").status_code, 404)
        with SessionLocal() as db:
            self.assertEqual(db.query(models.Expense).count(), 0)
            self.assertEqual(db.query(models.ListBookmark).count(), 0)

    def test_delete_unknown_list_is_404(self) -> None:
        self.assertEqual(self.client.delete(f"/api/lists/{uuid.uuid4()}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
