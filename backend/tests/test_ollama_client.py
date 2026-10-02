"""Tests fuer die Modell-spezifischen Chat-Optionen des Ollama-Clients.

Ausfuehren (im backend-Ordner; braucht httpx + pillow + pydantic):

    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


if __name__ == "__main__":
    unittest.main()
