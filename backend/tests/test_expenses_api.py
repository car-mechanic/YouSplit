"""Tests fuer die Ausgaben-Endpoints (CRUD, Duplikate, Kurs, Kassensturz, Import).

Ausfuehren (im backend-Ordner; braucht fastapi + sqlalchemy + httpx, nutzt SQLite):

    python -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest
import uuid
from unittest import mock

_DB_DIR = tempfile.mkdtemp(prefix="yousplit-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_DIR}/test.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import models  # noqa: E402,F401
from currency import ExchangeRateError  # noqa: E402
from database import Base, engine  # noqa: E402
from routers import lists, members  # noqa: E402


def expense(**overrides) -> dict:
    body = {
        "title": "Rewe",
        "amount": 24.5,
        "payer_name": "Kev",
        "receipt_date": "2026-10-01",
    }
    body.update(overrides)
    return body


class ExpensesApiTest(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        app = FastAPI()
        app.include_router(lists.router, prefix="/api")
        app.include_router(members.router, prefix="/api")
        self.client = TestClient(app)
        self.list_id = self.client.post("/api/lists", json={"title": "WG"}).json()["id"]
        self.url = f"/api/lists/{self.list_id}/expenses"

    def post(self, **overrides):
        return self.client.post(self.url, json=expense(**overrides))

    # ---------- Anlegen ----------

    def test_anlegen_und_in_der_liste_wiederfinden(self) -> None:
        response = self.post()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["currency"], "EUR")
        self.assertEqual(body["exchange_rate"], 1.0)
        stored = self.client.get(f"/api/lists/{self.list_id}").json()["expenses"]
        self.assertEqual([e["id"] for e in stored], [body["id"]])

    def test_unbekannte_liste_ist_404(self) -> None:
        response = self.client.post(
            f"/api/lists/{uuid.uuid4()}/expenses", json=expense()
        )
        self.assertEqual(response.status_code, 404)

    def test_ungueltige_eingaben_sind_422(self) -> None:
        faelle = {
            "betrag 0": {"amount": 0},
            "betrag negativ": {"amount": -5},
            "betrag nan": {"amount": "NaN"},
            "titel leer": {"title": ""},
            "titel nur leerzeichen": {"title": "   "},
            "zahler nur leerzeichen": {"payer_name": "   "},
            "ratio zu gross": {"split_ratio": 1.5},
            "unbekannte waehrung": {"currency": "XYZ"},
            "splits summe falsch": {"splits": {"Kev": 1.0, "Anna": 1.0}},
            "splits negativ": {"splits": {"Kev": 30.0, "Anna": -5.5}},
        }
        for name, overrides in faelle.items():
            with self.subTest(name):
                self.assertEqual(self.post(**overrides).status_code, 422)

    def test_namen_werden_getrimmt_gespeichert(self) -> None:
        # Sonst waere "Kev " im Kassensturz eine zweite Person neben "Kev"
        body = self.post(title="  Rewe ", payer_name=" Kev ").json()
        self.assertEqual(body["title"], "Rewe")
        self.assertEqual(body["payer_name"], "Kev")

    def test_splits_werden_gespeichert(self) -> None:
        body = self.post(splits={"Kev": 10.0, "Anna": 14.5}).json()
        self.assertEqual(body["splits"], {"Kev": 10.0, "Anna": 14.5})

    # ---------- Duplikate ----------

    def test_duplikat_wird_mit_409_abgelehnt_und_mit_force_gespeichert(self) -> None:
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(self.post(title="Anderer Laden").status_code, 409)
        self.assertEqual(
            self.client.post(self.url + "?force=true", json=expense()).status_code, 201
        )

    def test_anderer_betrag_oder_tag_ist_kein_duplikat(self) -> None:
        self.post()
        self.assertEqual(self.post(amount=24.51).status_code, 201)
        self.assertEqual(self.post(receipt_date="2026-10-02").status_code, 201)

    def test_duplikat_pruefung_gilt_nur_je_liste(self) -> None:
        self.post()
        other = self.client.post("/api/lists", json={"title": "Reise"}).json()["id"]
        response = self.client.post(f"/api/lists/{other}/expenses", json=expense())
        self.assertEqual(response.status_code, 201)

    # ---------- Wechselkurs ----------

    def test_fremdwaehrung_speichert_den_tageskurs(self) -> None:
        with mock.patch.object(lists, "get_exchange_rate", mock.AsyncMock(return_value=0.9)):
            body = self.post(currency="usd").json()
        self.assertEqual(body["currency"], "USD")
        self.assertEqual(body["exchange_rate"], 0.9)

    def test_kursausfall_ist_502_und_speichert_nichts(self) -> None:
        failing = mock.AsyncMock(side_effect=ExchangeRateError("offline"))
        with mock.patch.object(lists, "get_exchange_rate", failing):
            response = self.post(currency="USD")
        self.assertEqual(response.status_code, 502)
        stored = self.client.get(f"/api/lists/{self.list_id}").json()["expenses"]
        self.assertEqual(stored, [])

    # ---------- Bearbeiten / Loeschen ----------

    def put(self, expense_id: str, **overrides):
        body = expense(category="Lebensmittel")
        body.update(overrides)
        return self.client.put(f"{self.url}/{expense_id}", json=body)

    def test_bearbeiten_ersetzt_die_felder(self) -> None:
        created = self.post().json()
        response = self.put(
            created["id"], title="Edeka", amount=10.0, splits={"Kev": 4.0, "Anna": 6.0}
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual((body["title"], body["amount"]), ("Edeka", 10.0))
        self.assertEqual(body["splits"], {"Kev": 4.0, "Anna": 6.0})
        self.assertEqual(body["category"], "Lebensmittel")

    def test_bearbeiten_ohne_splits_entfernt_die_aufteilung(self) -> None:
        created = self.post(splits={"Kev": 10.0, "Anna": 14.5}).json()
        self.assertIsNone(self.put(created["id"]).json()["splits"])

    def test_waehrungswechsel_holt_neuen_kurs_gleiche_waehrung_nicht(self) -> None:
        created = self.post().json()
        rate = mock.AsyncMock(return_value=1.25)
        with mock.patch.object(lists, "get_exchange_rate", rate):
            self.assertEqual(self.put(created["id"], currency="GBP").json()["exchange_rate"], 1.25)
            self.assertEqual(rate.await_count, 1)
            self.put(created["id"], currency="GBP")
            self.assertEqual(rate.await_count, 1)

    def test_fremde_oder_unbekannte_ausgabe_ist_404(self) -> None:
        created = self.post().json()
        other = self.client.post("/api/lists", json={"title": "Reise"}).json()["id"]
        wrong_list = f"/api/lists/{other}/expenses/{created['id']}"
        self.assertEqual(self.client.delete(wrong_list).status_code, 404)
        self.assertEqual(self.put(str(uuid.uuid4())).status_code, 404)

    def test_loeschen(self) -> None:
        created = self.post().json()
        self.assertEqual(self.client.delete(f"{self.url}/{created['id']}").status_code, 204)
        self.assertEqual(self.client.delete(f"{self.url}/{created['id']}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/lists/{self.list_id}").json()["expenses"], [])

    # ---------- Kassensturz ----------

    def test_kassensturz_endpoint(self) -> None:
        self.client.put(f"/api/lists/{self.list_id}/members", json={"members": ["Kev", "Anna"]})
        self.post(amount=40.0, splits={"Kev": 20.0, "Anna": 20.0})
        body = self.client.get(f"/api/lists/{self.list_id}/settlement").json()
        self.assertEqual(
            body["transactions"],
            [{"from_person": "Anna", "to_person": "Kev", "amount": 20.0}],
        )

    def test_kassensturz_unbekannte_liste_ist_404(self) -> None:
        response = self.client.get(f"/api/lists/{uuid.uuid4()}/settlement")
        self.assertEqual(response.status_code, 404)

    # ---------- Kontoauszug-Import ----------

    def import_items(self, **overrides):
        body = {
            "payer_name": "Kev",
            "items": [
                {"title": "Rewe", "amount": 10.0, "booking_date": "2026-10-01"},
                {"title": "Lidl", "amount": 5.0},
            ],
        }
        body.update(overrides)
        return self.client.post(f"/api/lists/{self.list_id}/bank-statement/import", json=body)

    def test_import_legt_ausgaben_fair_verteilt_an(self) -> None:
        self.client.put(
            f"/api/lists/{self.list_id}/members", json={"members": ["Kev", "Anna", "Tom"]}
        )
        response = self.import_items(payer_name="Anna")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"created": 2, "total": 15.0})
        stored = self.client.get(f"/api/lists/{self.list_id}").json()["expenses"]
        self.assertEqual(len(stored), 2)
        for item in stored:
            self.assertEqual(item["category"], "Lebensmittel")
            self.assertEqual(item["payer_name"], "Anna")
            self.assertAlmostEqual(sum(item["splits"].values()), item["amount"], places=2)
            self.assertEqual(set(item["splits"]), {"Kev", "Anna", "Tom"})

    def test_import_nimmt_unbekannten_zahler_als_person_auf(self) -> None:
        self.import_items(payer_name="Neu")
        stored = self.client.get(f"/api/lists/{self.list_id}").json()["expenses"]
        self.assertEqual(set(stored[0]["splits"]), {"Neu"})
        self.assertEqual(stored[0]["split_ratio"], 1.0)

    def test_import_ungueltige_eingaben(self) -> None:
        self.assertEqual(self.import_items(items=[]).status_code, 422)
        bad_amount = [{"title": "x", "amount": 0}]
        self.assertEqual(self.import_items(items=bad_amount).status_code, 422)
        self.assertEqual(self.import_items(payer_name="  ").status_code, 422)


if __name__ == "__main__":
    unittest.main()
