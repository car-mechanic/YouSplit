"""Tests fuer die Wechselkurs-Abfrage (Frankfurter-API wird durch einen Mock ersetzt).

Ausfuehren (im backend-Ordner):

    python -m unittest discover -s tests -v
"""

import asyncio
import os
import sys
import unittest
from unittest import mock

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import currency  # noqa: E402


def _client_factory(handler):
    """Ersetzt ``httpx.AsyncClient`` durch einen Client mit Mock-Transport."""
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    return factory


def fetch(currency_code: str, handler) -> float:
    with mock.patch.object(currency.httpx, "AsyncClient", _client_factory(handler)):
        return asyncio.run(currency.get_exchange_rate(currency_code))


class ExchangeRateTest(unittest.TestCase):
    def test_eur_braucht_keinen_api_aufruf(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("EUR darf die API nicht aufrufen")

        self.assertEqual(fetch(" eur ", handler), 1.0)

    def test_kurs_wird_aus_der_antwort_gelesen(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json={"rates": {"EUR": 0.92}})

        self.assertEqual(fetch("usd", handler), 0.92)
        self.assertEqual(seen[0].url.params["from"], "USD")
        self.assertEqual(seen[0].url.params["to"], "EUR")

    def test_fehler_werden_zu_exchange_rate_error(self) -> None:
        faelle = {
            "http 500": lambda r: httpx.Response(500),
            "kein json": lambda r: httpx.Response(200, text="<html>"),
            "ohne eur-schluessel": lambda r: httpx.Response(200, json={"rates": {}}),
            "rates null": lambda r: httpx.Response(200, json={"rates": None}),
            "kurs null": lambda r: httpx.Response(200, json={"rates": {"EUR": None}}),
            "kurs text": lambda r: httpx.Response(200, json={"rates": {"EUR": "abc"}}),
            "kurs null wert": lambda r: httpx.Response(200, json={"rates": {"EUR": 0}}),
            "kurs negativ": lambda r: httpx.Response(200, json={"rates": {"EUR": -1.5}}),
        }
        for name, handler in faelle.items():
            with self.subTest(name):
                with self.assertRaises(currency.ExchangeRateError):
                    fetch("USD", handler)

    def test_netzwerkfehler_wird_zu_exchange_rate_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("offline")

        with self.assertRaises(currency.ExchangeRateError):
            fetch("USD", handler)


if __name__ == "__main__":
    unittest.main()
