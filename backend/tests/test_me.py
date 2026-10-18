"""Tests fuer HA-Benutzer (Ingress-Header), „Meine Listen“ und die Verknuepfung
von Personen mit HA-Benutzern.

Ausfuehren (im backend-Ordner; braucht fastapi + sqlalchemy + httpx, nutzt SQLite):

    python -m unittest discover -s tests -v
"""

import asyncio
import json
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
from websockets.asyncio.server import ServerConnection, serve  # noqa: E402

import ha_users  # noqa: E402
from database import Base, engine  # noqa: E402
from ha_identity import INGRESS_PROXY_IP  # noqa: E402
from routers import lists, me, members  # noqa: E402

KEV = "a1" * 16
ANNA = "b2" * 16


def _user_headers(user_id: str, display_name: str = "Kev") -> dict[str, bytes]:
    # Wie der Supervisor: Werte als UTF-8-Bytes (httpx kodiert str als ASCII)
    return {
        "X-Remote-User-Id": user_id.encode(),
        "X-Remote-User-Name": display_name.lower().encode("utf-8"),
        "X-Remote-User-Display-Name": display_name.encode("utf-8"),
    }


class MeApiTest(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        app = FastAPI()
        app.include_router(lists.router, prefix="/api")
        app.include_router(members.router, prefix="/api")
        app.include_router(me.router, prefix="/api")
        # Ingress-Anfragen kommen vom Supervisor, alles andere ist der direkte Port
        self.ingress = TestClient(app, client=(INGRESS_PROXY_IP, 50000))
        self.direct = TestClient(app, client=("192.168.1.20", 50000))

    def new_list(self, title: str = "WG") -> str:
        return self.direct.post("/api/lists", json={"title": title}).json()["id"]

    def my_lists(self, user_id: str = KEV) -> list[dict]:
        response = self.ingress.get("/api/me/lists", headers=_user_headers(user_id))
        self.assertEqual(response.status_code, 200)
        return response.json()

    # ---------- Identitaet ----------

    def test_ingress_liefert_benutzer_mit_umlauten(self) -> None:
        response = self.ingress.get("/api/me", headers=_user_headers(KEV, "Jörg"))
        self.assertEqual(
            response.json(), {"id": KEV, "name": "jörg", "display_name": "Jörg"}
        )

    def test_header_vom_direkten_port_werden_ignoriert(self) -> None:
        # Sonst koennte sich jeder im LAN als beliebiger HA-Benutzer ausgeben
        self.assertIsNone(self.direct.get("/api/me", headers=_user_headers(KEV)).json())
        response = self.direct.get("/api/me/lists", headers=_user_headers(KEV))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.direct.get("/api/ha/users").status_code, 401)

    def test_ingress_ohne_benutzer(self) -> None:
        self.assertIsNone(self.ingress.get("/api/me").json())

    # ---------- Meine Listen ----------

    def test_besuchte_liste_ist_auf_jedem_geraet_sichtbar(self) -> None:
        list_id = self.new_list("Urlaub")
        visit = self.ingress.put(f"/api/me/lists/{list_id}", headers=_user_headers(KEV))
        self.assertEqual(visit.status_code, 204)
        mine = self.my_lists()
        self.assertEqual([(m["id"], m["title"], m["is_member"]) for m in mine],
                         [(list_id, "Urlaub", False)])
        self.assertIsNotNone(mine[0]["last_visit"])
        # Andere Benutzer sehen die Liste nicht
        self.assertEqual(self.my_lists(ANNA), [])

    def test_zuletzt_besuchte_liste_steht_vorne(self) -> None:
        first, second = self.new_list("A"), self.new_list("B")
        for list_id in (first, second, first):
            self.ingress.put(f"/api/me/lists/{list_id}", headers=_user_headers(KEV))
        self.assertEqual([m["title"] for m in self.my_lists()], ["A", "B"])

    def test_verknuepfte_person_sieht_liste_ohne_besuch(self) -> None:
        list_id = self.new_list()
        self.direct.put(
            f"/api/lists/{list_id}/members",
            json={"members": ["Kev", "Anna"], "member_users": {"Anna": ANNA}},
        )
        mine = self.my_lists(ANNA)
        self.assertEqual([(m["id"], m["is_member"], m["last_visit"]) for m in mine],
                         [(list_id, True, None)])

    def test_entfernen_loescht_nur_den_eintrag(self) -> None:
        list_id = self.new_list()
        self.ingress.put(f"/api/me/lists/{list_id}", headers=_user_headers(KEV))
        response = self.ingress.delete(f"/api/me/lists/{list_id}", headers=_user_headers(KEV))
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.my_lists(), [])
        self.assertEqual(self.direct.get(f"/api/lists/{list_id}").status_code, 200)

    def test_besuch_unbekannter_liste(self) -> None:
        response = self.ingress.put(f"/api/me/lists/{uuid.uuid4()}", headers=_user_headers(KEV))
        self.assertEqual(response.status_code, 404)

    def test_import_der_geraete_merkliste(self) -> None:
        known, visited = self.new_list("Lokal"), self.new_list("Schon da")
        self.ingress.put(f"/api/me/lists/{visited}", headers=_user_headers(KEV))
        before = self.my_lists()[0]["last_visit"]
        response = self.ingress.post(
            "/api/me/lists/import",
            json={"list_ids": [known, visited, str(uuid.uuid4())]},
            headers=_user_headers(KEV),
        )
        self.assertEqual(response.status_code, 204)
        mine = {m["title"]: m["last_visit"] for m in self.my_lists()}
        self.assertEqual(set(mine), {"Lokal", "Schon da"})
        # Bestehender Eintrag behaelt seinen Zeitstempel
        self.assertEqual(mine["Schon da"], before)

    # ---------- Verknuepfung Person ↔ HA-Benutzer ----------

    def test_verknuepfung_wird_gespeichert_und_geliefert(self) -> None:
        list_id = self.new_list()
        response = self.direct.put(
            f"/api/lists/{list_id}/members",
            json={"members": [" Kev ", "Anna"], "member_users": {" Kev ": KEV}},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["member_users"], {"Kev": KEV})
        stored = self.direct.get(f"/api/lists/{list_id}").json()
        self.assertEqual(stored["member_users"], {"Kev": KEV})

    def test_neue_liste_hat_keine_verknuepfungen(self) -> None:
        list_id = self.new_list()
        self.assertEqual(self.direct.get(f"/api/lists/{list_id}").json()["member_users"], {})

    def test_ungueltige_verknuepfungen(self) -> None:
        list_id = self.new_list()
        cases = [
            {"members": ["Kev"], "member_users": {"Tom": KEV}},  # keine Person
            {"members": ["Kev", "Anna"], "member_users": {"Kev": KEV, "Anna": KEV}},
            {"members": ["Kev"], "member_users": {"Kev": " "}},
        ]
        for body in cases:
            with self.subTest(body=body):
                response = self.direct.put(f"/api/lists/{list_id}/members", json=body)
                self.assertEqual(response.status_code, 422)

    def test_alte_clients_ohne_verknuepfung_loeschen_sie(self) -> None:
        list_id = self.new_list()
        url = f"/api/lists/{list_id}/members"
        self.direct.put(url, json={"members": ["Kev"], "member_users": {"Kev": KEV}})
        self.direct.put(url, json={"members": ["Kev"]})
        self.assertEqual(self.direct.get(f"/api/lists/{list_id}").json()["member_users"], {})

    # ---------- HA-Benutzerliste ----------

    def test_ha_benutzer_ueber_ingress(self) -> None:
        users = [ha_users.HaUserOption(id=KEV, name="Kev")]
        with mock.patch("routers.me.fetch_users", mock.AsyncMock(return_value=users)):
            response = self.ingress.get("/api/ha/users", headers=_user_headers(KEV))
        self.assertEqual(response.json(), [{"id": KEV, "name": "Kev"}])

    def test_ha_benutzer_nicht_erreichbar(self) -> None:
        failing = mock.AsyncMock(side_effect=ha_users.HaUsersError("weg"))
        with mock.patch("routers.me.fetch_users", failing):
            response = self.ingress.get("/api/ha/users", headers=_user_headers(KEV))
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "weg")


class SelectableUsersTest(unittest.TestCase):
    def test_nur_aktive_echte_benutzer_sortiert(self) -> None:
        raw = [
            {"id": "1", "name": "Zoe", "username": "zoe", "is_active": True,
             "system_generated": False},
            {"id": "2", "name": "Supervisor", "username": None, "is_active": True,
             "system_generated": True},
            {"id": "3", "name": "Alt", "username": "alt", "is_active": False,
             "system_generated": False},
            {"id": "4", "name": "", "username": "anna", "is_active": True,
             "system_generated": False},
        ]
        self.assertEqual(
            ha_users.selectable_users(raw),
            [ha_users.HaUserOption("4", "anna"), ha_users.HaUserOption("1", "Zoe")],
        )

    def test_ohne_supervisor_token(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ha_users.HaUsersError):
                asyncio.run(ha_users.fetch_users())


class CoreWebsocketTest(unittest.TestCase):
    """Spielt das Websocket-Protokoll von Home Assistant Core lokal nach."""

    def run_against_fake_core(self, token: str) -> list[ha_users.HaUserOption]:
        async def core(websocket: ServerConnection) -> None:
            await websocket.send(json.dumps({"type": "auth_required"}))
            auth = json.loads(await websocket.recv())
            if auth["access_token"] != "geheim":
                await websocket.send(json.dumps({"type": "auth_invalid"}))
                return
            await websocket.send(json.dumps({"type": "auth_ok"}))
            command = json.loads(await websocket.recv())
            assert command["type"] == "config/auth/list"
            await websocket.send(json.dumps({
                "id": command["id"], "type": "result", "success": True,
                "result": [{"id": KEV, "name": "Kev", "username": "kev",
                            "is_active": True, "system_generated": False}],
            }))

        async def scenario() -> list[ha_users.HaUserOption]:
            async with serve(core, "127.0.0.1", 0) as server:
                port = server.sockets[0].getsockname()[1]
                with (
                    mock.patch.object(
                        ha_users, "CORE_WEBSOCKET_URL", f"ws://127.0.0.1:{port}"
                    ),
                    mock.patch.dict(os.environ, {"SUPERVISOR_TOKEN": token}),
                ):
                    return await ha_users.fetch_users()

        return asyncio.run(scenario())

    def test_benutzerliste_vom_core(self) -> None:
        self.assertEqual(
            self.run_against_fake_core("geheim"), [ha_users.HaUserOption(KEV, "Kev")]
        )

    def test_falsches_token(self) -> None:
        with self.assertRaises(ha_users.HaUsersError):
            self.run_against_fake_core("falsch")


if __name__ == "__main__":
    unittest.main()
