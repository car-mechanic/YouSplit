"""Tests fuer den Kontoauszug-Parser (reine Logik, ohne PDF/DB).

Ausfuehren (im backend-Ordner, ohne Zusatz-Pakete ausser pdfplumber):

    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bank_statement import (  # noqa: E402
    CATEGORY_FOOD,
    classify,
    load_food_merchants,
    parse_lines,
    parse_merchant_lines,
)


class ParseLinesTest(unittest.TestCase):
    def test_sparkasse_layout_zwei_daten_und_folgezeilen(self) -> None:
        lines = [
            "Kontoauszug Nr. 9/2026 vom 01.09.2026 bis 30.09.2026",
            "Buchungstag Valuta Vorgang Betrag",
            "Alter Kontostand 1.234,56",
            "01.09. 01.09. Kartenzahlung -45,67",
            "REWE SAGT DANKE//Berlin/DE",
            "02.09. 02.09. Gutschrift 2.500,00",
            "Gehalt September",
            "Neuer Kontostand 3.688,89",
        ]
        bookings = parse_lines(lines).bookings
        self.assertEqual(len(bookings), 2)
        self.assertEqual(bookings[0].booking_date, date(2026, 9, 1))
        self.assertAlmostEqual(bookings[0].amount, -45.67)
        self.assertIn("REWE SAGT DANKE", bookings[0].description)
        self.assertAlmostEqual(bookings[1].amount, 2500.00)

    def test_vorzeichen_hinten_und_soll_haben(self) -> None:
        lines = [
            "03.09.2026 Lastschrift LIDL SAGT DANKE 12,30-",
            "04.09.2026 Gutschrift Erstattung 5,00 H",
            "05.09.2026 Kartenzahlung EDEKA 7,10 S",
        ]
        amounts = [b.amount for b in parse_lines(lines).bookings]
        self.assertEqual(amounts, [-12.30, 5.00, -7.10])

    def test_ing_valuta_zeile_ist_fortsetzung(self) -> None:
        lines = [
            "01.09.2026 Lastschrift Aldi Sued -23,45",
            "01.09.2026 Mandat 12345 Referenz 987",
            "02.09.2026 Gutschrift Gehalt 100,00",
        ]
        bookings = parse_lines(lines).bookings
        self.assertEqual(len(bookings), 2)
        self.assertIn("Mandat", bookings[0].description)

    def test_betrags_und_saldospalte_nimmt_den_betrag(self) -> None:
        lines = [
            "Datum Text Betrag Saldo",
            "01.09.2026 Kartenzahlung PENNY -10,00 1.990,00",
        ]
        bookings = parse_lines(lines).bookings
        self.assertAlmostEqual(bookings[0].amount, -10.00)

    def test_unsigned_ist_gutschrift_wenn_ausgaben_mit_minus_stehen(self) -> None:
        lines = [
            "01.09. Kartenzahlung REWE -45,67",
            "02.09. Ueberweisung von Max Mustermann 50,00",
        ]
        result = parse_lines(lines)
        self.assertAlmostEqual(result.bookings[1].amount, 50.00)
        self.assertFalse(result.bookings[1].sign_guessed)
        self.assertFalse(result.warnings)

    def test_ohne_vorzeichen_wird_als_ausgabe_geraten(self) -> None:
        result = parse_lines(
            ["03.09.2026 Kartenzahlung NETTO 8,00", "04.09.2026 Gehalt 100,00"]
        )
        self.assertAlmostEqual(result.bookings[0].amount, -8.00)
        self.assertTrue(result.bookings[0].sign_guessed)
        self.assertAlmostEqual(result.bookings[1].amount, 100.00)
        self.assertTrue(result.warnings)

    def test_jahr_aus_kopfzeile_bei_datum_ohne_jahr(self) -> None:
        lines = ["Auszug vom 30.09.2026", "15.09. Kartenzahlung REWE -9,99"]
        self.assertEqual(
            parse_lines(lines).bookings[0].booking_date, date(2026, 9, 15)
        )

    def test_jahreswechsel_dezember_gehoert_ins_vorjahr(self) -> None:
        lines = [
            "Auszug vom 31.01.2026",
            "30.12. Kartenzahlung REWE -9,99",
            "02.01. Kartenzahlung REWE -5,00",
        ]
        dates = [b.booking_date for b in parse_lines(lines).bookings]
        self.assertEqual(dates, [date(2025, 12, 30), date(2026, 1, 2)])

    def test_seitenfuss_wird_nicht_zur_beschreibung(self) -> None:
        lines = [
            "01.09. Kartenzahlung REWE -9,99",
            "Seite 1 von 2",
            "Sparkasse Musterstadt",
        ]
        self.assertNotIn("Seite", parse_lines(lines).bookings[0].description)

    def test_betrag_in_folgezeile(self) -> None:
        lines = ["01.09.2026 Kartenzahlung KAUFLAND", "Filiale 123", "-31,40"]
        bookings = parse_lines(lines).bookings
        self.assertAlmostEqual(bookings[0].amount, -31.40)
        self.assertNotIn("31,40", bookings[0].description)


class ClassifyTest(unittest.TestCase):
    def test_haendlerliste(self) -> None:
        for text in (
            "KARTENZAHLUNG REWE SAGT DANKE",
            "Lastschrift EDEKA Neumann",
            "ALDI SUED 1234",
            "Bäckerei Müller",
            "PayPal *Lidl sagt Danke 35314369001",  # Zahlung ueber PayPal
            "E-Center Hamburg",
            "INTERMARCHÉ SUPER 4711",  # Akzente
            "Tesco Superstore London",
            "WOOLWORTHS 1234 SYDNEY",
        ):
            self.assertEqual(classify(text).category, CATEGORY_FOOD, text)

    def test_zusammengesetzte_woerter_mit_stern(self) -> None:
        for text, label in (
            ("Landfleischerei Schmidt", "Landfleischerei"),
            ("Kartenzahlung Hofmetzgerei Maier", "Hofmetzgerei"),
            ("Getränkemarkt Nord", "Getränkemarkt"),
        ):
            result = classify(text)
            self.assertTrue(result.is_food, text)
            self.assertEqual(result.label, label)

    def test_eigene_eintraege_scholand(self) -> None:
        result = classify("Kartenzahlung Scholand Einzelhan Hamburg")
        self.assertTrue(result.is_food)
        self.assertEqual(result.label, "Scholand")

    def test_drogerie_zaehlt_mit(self) -> None:
        self.assertTrue(classify("DM Drogerie Markt Filiale 123").is_food)
        self.assertTrue(classify("dm-drogerie markt").is_food)
        self.assertTrue(classify("ROSSMANN 1234").is_food)

    def test_nur_ganze_woerter(self) -> None:
        # SPAR darf nicht in SPARKASSE/SPARPLAN treffen
        self.assertIsNone(classify("Sparkasse Entgelt Kontofuehrung").category)
        self.assertIsNone(classify("Sparplan ETF").category)
        self.assertEqual(classify("SPAR Express Wien").category, CATEGORY_FOOD)

    def test_keine_fehlalarme_bei_alltagsbuchungen(self) -> None:
        for text in (
            "Miete September",
            "SPOTIFY AB",
            "Netflix.com",
            "AMAZON EU SARL",
            "Deutsche Bahn Ticket",
            "Telekom Deutschland GmbH",
            "Shell Tankstelle",
            "Apotheke am Markt",
            "Zalando SE",
            "LIEFERANDO.DE",
            "Gehalt Musterfirma GmbH",
            "Versicherung Haftpflicht",
            "Kontofuehrung Entgelt",
            "Barauszahlung Geldautomat",
        ):
            self.assertIsNone(classify(text).category, text)

    def test_regel_hat_vorrang_und_laengstes_stichwort_gewinnt(self) -> None:
        rules = [("REWE", "Sonstiges"), ("MEIN LADEN", CATEGORY_FOOD)]
        self.assertEqual(classify("REWE Markt", rules).category, "Sonstiges")
        self.assertTrue(classify("Zahlung Mein Laden", rules).is_food)


class MerchantListTest(unittest.TestCase):
    def test_zeilenformat(self) -> None:
        entries = parse_merchant_lines(
            [
                "# Kommentar",
                "",
                "REWE            # Supermarkt",
                "*FLEISCHEREI",
                "E-Center",
                "rewe",  # Duplikat (Gross/Klein egal)
            ]
        )
        self.assertEqual(
            [(e.keyword, e.substring) for e in entries],
            [("REWE", False), ("FLEISCHEREI", True), ("E CENTER", False)],
        )

    def test_mitgelieferte_datei_ist_sauber(self) -> None:
        entries = load_food_merchants()
        self.assertGreater(len(entries), 200)
        # zu kurze Stichwoerter waeren Fehlalarm-Quellen (ausser bewusst bekannte)
        short = [e.keyword for e in entries if len(e.keyword) < 3]
        self.assertEqual(short, [], short)


if __name__ == "__main__":
    unittest.main()
