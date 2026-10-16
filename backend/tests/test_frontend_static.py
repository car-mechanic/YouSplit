"""Tests fuer die Frontend-Auslieferung im Add-on (Ingress-Basis, Share-URL).

Ausfuehren (im backend-Ordner):

    python -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from frontend_static import BASE_TAG, PUBLIC_URL_META, register_frontend  # noqa: E402

INGRESS = "/api/hassio_ingress/AbC_123-x"


class FrontendStaticTest(unittest.TestCase):
    def setUp(self) -> None:
        self.static = tempfile.mkdtemp(prefix="yousplit-static-")
        with open(os.path.join(self.static, "index.html"), "w", encoding="utf-8") as f:
            f.write(f"<head>{BASE_TAG}{PUBLIC_URL_META}</head>")
        os.mkdir(os.path.join(self.static, "assets"))
        with open(os.path.join(self.static, "assets", "app.js"), "w") as f:
            f.write("js")

    def client(self, public_url: str = "") -> TestClient:
        app = FastAPI()
        register_frontend(app, self.static, public_url)
        return TestClient(app)

    def test_direkter_port_behaelt_basis_root(self) -> None:
        page = self.client().get("/list/abc").text
        self.assertIn('<base href="/" />', page)

    def test_ingress_setzt_basis_auf_praefix(self) -> None:
        page = self.client().get("/", headers={"X-Ingress-Path": INGRESS}).text
        self.assertIn(f'<base href="{INGRESS}/" />', page)

    def test_fremder_ingress_header_wird_ignoriert(self) -> None:
        evil = '/x" /><script>alert(1)</script>'
        page = self.client().get("/", headers={"X-Ingress-Path": evil}).text
        self.assertIn('<base href="/" />', page)
        self.assertNotIn("<script>", page)

    def test_index_html_direkt_bekommt_ebenfalls_basis(self) -> None:
        page = self.client().get("/index.html", headers={"X-Ingress-Path": INGRESS}).text
        self.assertIn(f'<base href="{INGRESS}/" />', page)

    def test_public_url_landet_escaped_im_meta_tag(self) -> None:
        page = self.client('https://split.example.org/"x').get("/").text
        self.assertIn('content="https://split.example.org/&quot;x"', page)

    def test_assets_und_api_404(self) -> None:
        client = self.client()
        self.assertEqual(client.get("/assets/app.js").text, "js")
        self.assertEqual(client.get("/api/unbekannt").status_code, 404)


if __name__ == "__main__":
    unittest.main()
