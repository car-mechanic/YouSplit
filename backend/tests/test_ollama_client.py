"""Tests fuer die Modell-spezifischen Chat-Optionen des Ollama-Clients.

Ausfuehren (im backend-Ordner; braucht httpx + pillow + pydantic):

    python -m unittest discover -s tests -v
"""

import asyncio
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402
from PIL import Image  # noqa: E402

import ollama_client  # noqa: E402
from ollama_client import thinking_options  # noqa: E402


class ThinkingOptionsTest(unittest.TestCase):
    def test_qwen3_modelle_bekommen_think_false(self) -> None:
        for model in ("qwen3.5:2b", "qwen3.5:4b", "qwen3-vl:2b", "Qwen3-VL:4B"):
            with self.subTest(model=model):
                self.assertEqual(thinking_options(model), {"think": False})

    def test_andere_modelle_bekommen_kein_think_feld(self) -> None:
        for model in ("qwen2.5vl:3b", "llava:7b", "gemma3:4b"):
            with self.subTest(model=model):
                self.assertEqual(thinking_options(model), {})


def _jpeg(width: int, height: int, orientation: int | None = None) -> bytes:
    image = Image.new("RGB", (width, height), "white")
    exif = Image.Exif()
    if orientation is not None:
        exif[0x0112] = orientation  # EXIF-Tag "Orientation"
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


class PrepareImageTest(unittest.TestCase):
    def size_after_prepare(self, data: bytes) -> tuple[int, int]:
        return Image.open(io.BytesIO(ollama_client._prepare_image(data))).size

    def test_bild_ohne_exif_bleibt_wie_es_ist(self) -> None:
        self.assertEqual(self.size_after_prepare(_jpeg(40, 20)), (40, 20))

    def test_hochkant_foto_wird_nach_exif_aufgerichtet(self) -> None:
        # Orientation 6 = Kamera lag quer, Bild ist um 90° zu drehen
        self.assertEqual(
            self.size_after_prepare(_jpeg(40, 20, orientation=6)), (20, 40)
        )

    def test_ergebnis_traegt_keine_drehung_mehr(self) -> None:
        prepared = ollama_client._prepare_image(_jpeg(40, 20, orientation=6))
        self.assertIsNone(Image.open(io.BytesIO(prepared)).getexif().get(0x0112))

    def test_grosse_bilder_werden_verkleinert(self) -> None:
        width, height = self.size_after_prepare(_jpeg(3000, 2000))
        self.assertLessEqual(width * height, ollama_client.MAX_IMAGE_PIXELS)

    def test_kein_bild_ergibt_verstaendlichen_fehler(self) -> None:
        with self.assertRaises(ollama_client.ReceiptAnalysisError):
            ollama_client._prepare_image(b"kein bild")


class AnalyzeReceiptTest(unittest.TestCase):
    """Nachbearbeitung der Modell-Antwort (Ollama selbst ist ersetzt)."""

    def setUp(self) -> None:
        self._orig = ollama_client._post_chat

    def tearDown(self) -> None:
        ollama_client._post_chat = self._orig

    def analyze(self, answer: dict) -> ollama_client.ReceiptAnalysis:
        async def fake_post_chat(_: dict) -> httpx.Response:
            return httpx.Response(
                200, json={"message": {"content": json.dumps(answer)}}
            )

        ollama_client._post_chat = fake_post_chat
        return asyncio.run(ollama_client.analyze_receipt(_jpeg(40, 20)))

    def answer(self, **overrides: object) -> dict:
        data: dict = {
            "title": "Lidl",
            "amount": "1.137,77 €",
            "date": "05.12.2025",
            "category": "Lebensmittel",
            "currency": "EUR",
        }
        data.update(overrides)
        return data

    def test_antwort_wird_gelesen(self) -> None:
        analysis = self.analyze(self.answer())
        self.assertEqual(analysis.title, "Lidl")
        self.assertAlmostEqual(analysis.amount, 1137.77)
        self.assertEqual(analysis.receipt_date.isoformat(), "2025-12-05")

    def test_leerer_titel_bekommt_einen_ersatznamen(self) -> None:
        for title in ("", "   "):
            with self.subTest(title=title):
                analysis = self.analyze(self.answer(title=title))
                self.assertEqual(analysis.title, ollama_client.FALLBACK_TITLE)

    def test_ueberlanger_titel_wird_auf_die_spaltenbreite_gekuerzt(self) -> None:
        self.assertEqual(len(self.analyze(self.answer(title="x" * 300)).title), 200)

    def test_unbekannte_kategorie_faellt_auf_den_fallback(self) -> None:
        analysis = self.analyze(self.answer(category="Elektronik"))
        self.assertEqual(analysis.category, "Sonstiges")

    def test_alte_kategorie_namen_werden_umbenannt(self) -> None:
        self.assertEqual(
            self.analyze(self.answer(category="Restaurant")).category, "Auswärtsessen"
        )
        self.assertEqual(
            self.analyze(self.answer(category="Kosmetik")).category, "Drogerie"
        )

    def test_prompt_nennt_genau_die_standard_kategorien(self) -> None:
        for category in ("Lebensmittel", "Auswärtsessen", "Mobilität", "Sonstiges"):
            self.assertIn(category, ollama_client.RECEIPT_PROMPT)
        self.assertNotIn("Restaurant", ollama_client.RECEIPT_PROMPT)


if __name__ == "__main__":
    unittest.main()
