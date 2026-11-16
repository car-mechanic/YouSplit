"""Tests for remembered merchants (category rules) of the bank statement import.

Run (in the backend folder; uses SQLite):

    python -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest
import uuid
from datetime import date
from unittest import mock

_DB_DIR = tempfile.mkdtemp(prefix="yousplit-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_DIR}/test.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import models  # noqa: E402
from bank_statement import Booking, ParseResult  # noqa: E402
from category_rules import CATEGORY_IGNORE  # noqa: E402
from database import Base, SessionLocal, engine  # noqa: E402
from routers import lists  # noqa: E402
from schemas import MAX_CLASSIFY_TEXT_LENGTH, MAX_CLASSIFY_TEXTS  # noqa: E402

OWNER_TEXT = "Kartenzahlung Hans Meier e.K. Musterstadt 12.03. Karte 1234"


class CategoryRulesApiTest(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        app = FastAPI()
        app.include_router(lists.router, prefix="/api")
        self.client = TestClient(app)
        self.list_id = self.client.post("/api/lists", json={"title": "WG"}).json()["id"]
        self.other_id = self.client.post("/api/lists", json={"title": "Urlaub"}).json()["id"]

    def url(self, list_id: str | None = None) -> str:
        return f"/api/lists/{list_id or self.list_id}/category-rules"

    def save(self, keyword: str, category: str = "Lebensmittel", list_id=None):
        return self.client.post(
            self.url(list_id),
            json={"recipient_keyword": keyword, "category": category},
        )

    # ---------- create / update / list / delete ----------

    def test_create_trims_keyword_and_lists_it(self) -> None:
        response = self.save("  Hans   Meier e.K.  ")
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["recipient_keyword"], "Hans Meier e.K.")
        self.assertEqual(body["category"], "Lebensmittel")
        self.assertEqual(body["list_id"], self.list_id)

        listed = self.client.get(self.url()).json()
        self.assertEqual([r["recipient_keyword"] for r in listed], ["Hans Meier e.K."])

    def test_same_folded_keyword_updates_instead_of_duplicating(self) -> None:
        first = self.save("Hans Meier e.K.").json()
        response = self.save("HANS MEIER E K", CATEGORY_IGNORE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], first["id"])
        listed = self.client.get(self.url()).json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["category"], CATEGORY_IGNORE)
        self.assertEqual(listed[0]["recipient_keyword"], "HANS MEIER E K")

    def test_same_keyword_in_other_list_is_separate(self) -> None:
        self.save("Hans Meier")
        self.assertEqual(self.save("Hans Meier", list_id=self.other_id).status_code, 201)
        self.assertEqual(len(self.client.get(self.url()).json()), 1)
        self.assertEqual(len(self.client.get(self.url(self.other_id)).json()), 1)

    def test_delete_rule(self) -> None:
        rule_id = self.save("Hans Meier").json()["id"]
        response = self.client.delete(f"{self.url()}/{rule_id}")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get(self.url()).json(), [])
        again = self.client.delete(f"{self.url()}/{rule_id}")
        self.assertEqual(again.status_code, 404)

    # ---------- validation ----------

    def test_rejects_empty_and_too_short_keywords(self) -> None:
        self.assertEqual(self.save("   ").status_code, 422)
        for keyword in ("ab", "e.K", " - ", "a.b"):
            with self.subTest(keyword=keyword):
                response = self.save(keyword)
                self.assertEqual(response.status_code, 422)
                self.assertIn("mindestens 3", response.json()["detail"])
        self.assertEqual(self.save("Edk").status_code, 201)

    def test_rejects_unknown_category(self) -> None:
        response = self.save("Hans Meier", "Freizeit")
        self.assertEqual(response.status_code, 422)
        self.assertIn("Unbekannte Kategorie", response.json()["detail"])
        self.assertEqual(self.client.get(self.url()).json(), [])

    # ---------- access ----------

    def test_unknown_list_is_404(self) -> None:
        unknown = str(uuid.uuid4())
        self.assertEqual(self.client.get(self.url(unknown)).status_code, 404)
        self.assertEqual(self.save("Hans Meier", list_id=unknown).status_code, 404)

    def test_rule_of_other_list_cannot_be_deleted(self) -> None:
        rule_id = self.save("Hans Meier", list_id=self.other_id).json()["id"]
        response = self.client.delete(f"{self.url()}/{rule_id}")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(len(self.client.get(self.url(self.other_id)).json()), 1)

    def test_deleting_the_list_removes_its_rules(self) -> None:
        self.save("Hans Meier")
        self.client.delete(f"/api/lists/{self.list_id}")
        with SessionLocal() as db:
            self.assertEqual(db.query(models.CategoryRule).count(), 0)

    # ---------- effect on the import ----------

    def parse(self) -> list[dict]:
        result = ParseResult(
            bookings=[
                Booking(date(2026, 3, 12), OWNER_TEXT, -23.4),
                Booking(date(2026, 3, 13), "Lastschrift REWE Markt GmbH", -10.0),
            ]
        )
        with mock.patch.object(
            lists.bank_statement, "parse_statement", return_value=result
        ):
            response = self.client.post(
                f"/api/lists/{self.list_id}/bank-statement/parse",
                files={"statement": ("auszug.pdf", b"%PDF-1.7 test")},
            )
        self.assertEqual(response.status_code, 200)
        return response.json()["transactions"]

    def test_saved_rule_applies_on_next_parse(self) -> None:
        before = self.parse()
        self.assertFalse(before[0]["is_food"])
        self.assertTrue(before[1]["is_food"])

        self.save("Hans Meier e.K.")
        self.save("REWE", CATEGORY_IGNORE)
        after = self.parse()
        self.assertTrue(after[0]["is_food"])
        self.assertEqual(after[0]["label"], "Hans Meier E K")
        # The ignore rule corrects a false hit of the merchant list.
        self.assertFalse(after[1]["is_food"])
        self.assertEqual(after[1]["category"], CATEGORY_IGNORE)

    def test_classify_endpoint_uses_current_rules(self) -> None:
        url = f"/api/lists/{self.list_id}/bank-statement/classify"
        body = {"descriptions": [OWNER_TEXT, "Lastschrift REWE Markt GmbH"]}
        before = self.client.post(url, json=body).json()["results"]
        self.assertEqual([r["is_food"] for r in before], [False, True])

        self.save("Hans Meier")
        after = self.client.post(url, json=body).json()["results"]
        self.assertEqual([r["is_food"] for r in after], [True, True])
        self.assertEqual(after[0]["category"], "Lebensmittel")

        unknown = f"/api/lists/{uuid.uuid4()}/bank-statement/classify"
        self.assertEqual(self.client.post(unknown, json=body).status_code, 404)

    def test_classify_endpoint_limits_batch_and_text_length(self) -> None:
        url = f"/api/lists/{self.list_id}/bank-statement/classify"
        full = {"descriptions": ["REWE"] * MAX_CLASSIFY_TEXTS}
        self.assertEqual(self.client.post(url, json=full).status_code, 200)
        too_many = {"descriptions": ["REWE"] * (MAX_CLASSIFY_TEXTS + 1)}
        self.assertEqual(self.client.post(url, json=too_many).status_code, 422)
        too_long = {"descriptions": ["x" * (MAX_CLASSIFY_TEXT_LENGTH + 1)]}
        self.assertEqual(self.client.post(url, json=too_long).status_code, 422)


if __name__ == "__main__":
    unittest.main()
