"""Tests fuer die festen Personen einer Liste (members) und ihre Wirkung.

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
from database import Base, engine  # noqa: E402
from routers import lists, members  # noqa: E402
from settlement import calculate_settlement, collect_persons  # noqa: E402


class MembersApiTest(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        app = FastAPI()
        app.include_router(lists.router, prefix="/api")
        app.include_router(members.router, prefix="/api")
        self.client = TestClient(app)
        self.list_id = self.client.post("/api/lists", json={"title": "WG"}).json()["id"]

    def put_members(self, names: list[str]):
        return self.client.put(
            f"/api/lists/{self.list_id}/members", json={"members": names}
        )

    def test_neue_liste_hat_keine_personen(self) -> None:
        self.assertEqual(self.client.get(f"/api/lists/{self.list_id}").json()["members"], [])

    def test_personen_werden_bereinigt_gespeichert(self) -> None:
        response = self.put_members([" Kev ", "Anna", "", "Kev", "Tom"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["members"], ["Kev", "Anna", "Tom"])
        stored = self.client.get(f"/api/lists/{self.list_id}").json()["members"]
        self.assertEqual(stored, ["Kev", "Anna", "Tom"])

    def test_ungueltige_eingaben(self) -> None:
        self.assertEqual(self.put_members(["x" * 101]).status_code, 422)
        self.assertEqual(self.put_members([f"P{i}" for i in range(51)]).status_code, 422)
        unknown = self.client.put(f"/api/lists/{uuid.uuid4()}/members", json={"members": []})
        self.assertEqual(unknown.status_code, 404)

    def test_erste_ausgabe_wird_im_kassensturz_auf_alle_aufgeteilt(self) -> None:
        self.put_members(["Kev", "Anna", "Tom"])
        # Altdaten-Fall ohne splits: der Rest geht an die ANDEREN Personen der Liste
        self.client.post(
            f"/api/lists/{self.list_id}/expenses",
            json={"title": "Pizza", "amount": 90, "payer_name": "Kev", "split_ratio": 1 / 3},
        )
        settlement = self.client.get(f"/api/lists/{self.list_id}/settlement").json()
        balances = {b["name"]: b["net"] for b in settlement["balances"]}
        self.assertEqual(balances, {"Kev": 60.0, "Anna": -30.0, "Tom": -30.0})

    def test_person_ohne_ausgabe_steht_im_kassensturz(self) -> None:
        self.put_members(["Kev", "Anna"])
        settlement = self.client.get(f"/api/lists/{self.list_id}/settlement").json()
        self.assertEqual([b["name"] for b in settlement["balances"]], ["Kev", "Anna"])
        self.assertEqual(settlement["transactions"], [])

    def test_kontoauszug_import_teilt_auf_alle_personen(self) -> None:
        self.put_members(["Kev", "Anna", "Tom"])
        response = self.client.post(
            f"/api/lists/{self.list_id}/bank-statement/import",
            json={"payer_name": "Kev", "items": [{"title": "REWE", "amount": 30}]},
        )
        self.assertEqual(response.status_code, 201)
        expense = self.client.get(f"/api/lists/{self.list_id}").json()["expenses"][0]
        self.assertEqual(expense["splits"], {"Kev": 10.0, "Anna": 10.0, "Tom": 10.0})

class CollectPersonsTest(unittest.TestCase):
    def test_personen_der_liste_kommen_zuerst_ohne_doppelte(self) -> None:
        expense = models.Expense(
            payer_name="Anna", amount=10, split_ratio=0.5, exchange_rate=1.0,
            splits={"Anna": 5, "Max": 5},
        )
        self.assertEqual(
            collect_persons([expense], ["Kev", "Anna", "Kev"]), ["Kev", "Anna", "Max"]
        )

    def test_ohne_personen_bleibt_alles_wie_bisher(self) -> None:
        expense = models.Expense(
            payer_name="Anna", amount=10, split_ratio=0.5, exchange_rate=1.0, splits=None
        )
        self.assertEqual(collect_persons([expense]), ["Anna"])
        self.assertEqual(calculate_settlement([expense]).transactions, [])


if __name__ == "__main__":
    unittest.main()
