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
    _CMapTooLarge,
    _page_text,
    _parse_embedded_cmap,
    _patch_cid_font,
    _wrap_get_cmap_from_spec,
    classify,
    load_food_merchants,
    parse_lines,
    parse_merchant_lines,
    prepare_rules,
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

    def test_comdirect_finanzreport_layout(self) -> None:
        # Made-up example in the comdirect "Finanzreport" layout: booking and
        # value date on two lines, "Übertrag / Überweisung" as booking type,
        # page footer with "USt-ID" before the next page header.
        lines = [
            "Finanzreport Nr. 7 per 01.06.2026 - Seite 2",
            "Buchungstag Vorgang Auftraggeber/Empfänger Buchungstext Ausgang",
            "Valuta Referenz IBAN/BIC Eingang",
            "Alter Saldo 01.05.2026 +100,00",
            "04.05.2026 Lastschrift / Lidl sagt Danke Lidl sagt Danke, Musterstadt DE -12,34",
            "04.05.2026 Belastung Karte Nr. 1234 56XX XXXX 7890",
            "ABC123 Kartenzahlung",
            "05.05.2026 Übertrag / Erika Musterfrau Miete Mai -400,00",
            "05.05.2026 Überweisung DE00000000000000000000 End-to-End-Ref.:",
            "musterbank – Fusszeile USt-ID: DE000000000",
            "12345 Musterstadt",
            "Finanzreport Nr. 7 per 01.06.2026 - Seite 3",
            "Buchungstag Vorgang Auftraggeber/Empfänger Buchungstext Ausgang",
            "06.05.2026 Übertrag / Max Mustermann Lohn/Gehalt +1.500,00",
            "06.05.2026 Überweisung End-to-End-Ref.: nicht angegeben",
            "Neuer Saldo 01.06.2026 +1.187,66",
        ]
        result = parse_lines(lines)
        bookings = result.bookings
        self.assertEqual(
            [b.amount for b in bookings], [-12.34, -400.00, 1500.00]
        )
        self.assertEqual(
            [b.booking_date for b in bookings],
            [date(2026, 5, 4), date(2026, 5, 5), date(2026, 5, 6)],
        )
        self.assertTrue(classify(bookings[0].description).is_food)
        self.assertIn("Erika Musterfrau", bookings[1].description)
        self.assertNotIn("USt-ID", bookings[1].description)
        self.assertNotIn("Musterstadt", bookings[1].description)
        self.assertFalse(result.warnings)
        # Opening balance + bookings = closing balance
        self.assertAlmostEqual(100.00 + sum(b.amount for b in bookings), 1187.66)

    def test_uebertrag_ohne_schraegstrich_bleibt_saldozeile(self) -> None:
        lines = [
            "30.09.2026 Übertrag auf Blatt 2 1.234,56",
            "01.09. Kartenzahlung REWE -9,99",
        ]
        bookings = parse_lines(lines).bookings
        self.assertEqual([b.amount for b in bookings], [-9.99])

    def test_volksbank_closing_note_is_no_booking(self) -> None:
        # Made-up example in the Volksbank layout: after the closing balance an
        # attachment itemises the fees already booked as "Abschluss".
        lines = [
            "30.09. 30.09. Abschluss lt. Anlage 1 4,95 S",
            "neuer Kontostand vom 30.09.2026 1.000,00 H",
            "Anlage 1",
            "30.09.2026",
            "Wert: 30.09.2026",
            "Kontokorrentkredit vom 01.07.2026 bis 30.09.2026",
            "12,50000% Zinsen ab 30.09. 0,00 S",
            "Kontoführung 4,95 S",
            "Summe Abschluss in EUR 4,95 S",
        ]
        result = parse_lines(lines)
        self.assertEqual([b.amount for b in result.bookings], [-4.95])
        self.assertFalse(result.warnings)

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
        self.assertEqual(result.label, "Rewe")

    def test_rewe_franchise_yazici(self) -> None:
        # So steht der Markt im Kontoauszug (Betreiber statt Kette)
        for text in (
            "Kartenzahlung YAZICI EINZELHANDELS OHG//Hamburg/DE",
            "Yazici Einzelhandels oHG Hamburg",
        ):
            with self.subTest(text=text):
                result = classify(text)
                self.assertTrue(result.is_food)
                self.assertEqual(result.label, "Rewe")
        # Nur "Yazici" allein (z. B. ein anderes Geschaeft) trifft nicht
        self.assertFalse(classify("Yazici Schneiderei").is_food)

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

    def test_edeka_rewe_without_chain_name(self) -> None:
        # Abbreviations, formats, regional companies and independent merchants
        for text, label in (
            ("EDK SAGT DANKE 123", "Edeka"),
            ("EDK MUELLER OHG", "Edeka"),
            ("Kartenzahlung Zurheide Feine Kost Duesseldorf", "Edeka"),
            ("nahkauf Bergheim", "Rewe"),
            ("Lastschrift Nordbayern-Sachsen-Thüringen Stiftung", "Edeka"),
            ("EDEKA Südwest Stiftung & Co. KG", "Edeka"),
            ("REWE-Mokanski EH oHG Herne", "Rewe"),
            ("NP-Markt 4711 Hannover", "Edeka"),
            ("Simmel AG Chemnitz", "Edeka"),
            ("Simmel-Center Zwickau", "Edeka"),
            ("REWE Freidank oHG", "Rewe"),
            ("Markant Markt Hamburg", "Markant"),
        ):
            with self.subTest(text=text):
                result = classify(text)
                self.assertTrue(result.is_food)
                self.assertEqual(result.label, label)

    def test_ambiguous_merchant_names_need_context(self) -> None:
        # Edk only as a whole word; Markant/Simmel/Freidank only in fixed
        # phrases; Kaiser's/Tengelmann no longer exist (since 2017).
        for text in (
            "EDKA Versand",
            "Nord Immobilien GmbH",
            "Markant Immobilien",
            "Kaisers Kaffee",
            "Tengelmann Verwaltung",
            "Simmel Steuerberatung",
            "Freidank Rechtsanwaelte",
        ):
            with self.subTest(text=text):
                self.assertIsNone(classify(text).category)

    def test_owner_market_heuristic(self) -> None:
        # Strong sector words like "Supermarkt" or "E-Center" are already in
        # the merchant list; the heuristic covers the remaining formats.
        self.assertTrue(classify("Max Mustermann e.K. Frischemarkt").is_food)
        for text, label in (
            ("Max Mustermann e.K. SB Markt", "Max Mustermann"),
            ("Kartenzahlung 12.03 Hans Meier OHG Aktiv Markt", "Hans Meier"),
            ("PayPal *Schulze e.Kfm. Nah-Markt", "Schulze"),
            ("Mueller KG Frisch Markt", "Mueller"),
            ("Frische Center Hieber Bauer KG", "Hieber Bauer"),
            # Place names that merely contain a non-food stem
            ("Greifenberg Weber e.K. SB Markt", "Greifenberg Weber"),
            ("Blumenthal OHG Aktiv Markt", "Blumenthal"),
            ("Schuhmacher e.K. SB Markt", "Schuhmacher"),
        ):
            with self.subTest(text=text):
                result = classify(text)
                self.assertTrue(result.is_food)
                self.assertEqual(result.label, label)

    def test_owner_market_heuristic_rejects_false_hits(self) -> None:
        for text in (
            "Media Markt Hamburg GmbH & Co. KG",
            "Bauhaus GmbH & Co. KG Baumarkt",
            "Mustermann e.K.",  # legal form without a sector word
            "Elektro Markt Schmidt e.K.",
            "Moebel Center Meier KG",
            "Autohaus Center Huber GmbH & Co. KG",
            "Hagebaumarkt Mueller KG Markt",
            "Reifen Weber KG SB Markt",
            "Blumenladen Weber e.K. SB Markt",
            "Optiker Schulze OHG Nah Markt",
            # A bare "Center" is not a grocery sector word
            "Zahnarzt Center OHG",
            "Dental Center OHG",
            "Reha Center KG",
            "Kosmetik Center e.K.",
            "Hair Center e.K.",
            "Matratzen Center KG",
            "Bike Center KG",
            "Copy Center e.K.",
            "Sonnenstudio Center e.K.",
            "Musik Center e.K.",
            # A bare "Markt" needs a grocery hint
            "Ford Markt KG",
            "Max Mustermann e.K. Markt",
            # GmbH/UG/AG are not owner-market legal forms
            "Mustermann GmbH SB Markt",
            "Mustermann UG Frische Center",
            # A grocery hint only counts directly before "Markt"
            "SB Waschanlage Mueller KG Markt",
            "Schmidt KG Floh Markt SB",
            "SB Tankcenter Meier KG Markt",
            # Car wash, car parts, kiosk and TV shops are not groceries
            "Waschstrasse Meier OHG SB Markt",
            "Autoteile Frisch Markt Meier KG",
            "Kiosk Nah Markt Meier e.K.",
            "Fernsehtechnik Meier KG SB Markt",
        ):
            with self.subTest(text=text):
                self.assertIsNone(classify(text).category)

    def test_owner_market_label_stops_at_sector_words(self) -> None:
        # Sector words are not part of the owner's name; without a name
        # left the heuristic gives up instead of inventing a title.
        for text in (
            "Kiosk Markt OHG",
            "Kiosk SB Markt OHG",
            "SB Markt e.K.",
            "Markt e.K.",
            "Frische Center OHG",
            "Kartenzahlung Aktiv Markt KG",
        ):
            with self.subTest(text=text):
                self.assertIsNone(classify(text).category)
        result = classify("Nah Markt Meier e.K.")
        self.assertTrue(result.is_food)
        self.assertEqual(result.label, "Meier")

    def test_user_rule_beats_heuristic(self) -> None:
        rules = [("MUSTERMANN", "Sonstiges")]
        result = classify("Max Mustermann e.K. SB Markt", rules)
        self.assertEqual(result.category, "Sonstiges")

    def test_regel_hat_vorrang_und_laengstes_stichwort_gewinnt(self) -> None:
        rules = [("REWE", "Sonstiges"), ("MEIN LADEN", CATEGORY_FOOD)]
        self.assertEqual(classify("REWE Markt", rules).category, "Sonstiges")
        self.assertTrue(classify("Zahlung Mein Laden", rules).is_food)

    def test_prepared_rules_match_like_raw_rules(self) -> None:
        rules = [("Hans Meier e.K.", "Sonstiges"), ("...", CATEGORY_FOOD)]
        prepared = prepare_rules(rules)
        # Keywords are folded once; one that folds to nothing is dropped.
        self.assertEqual(prepared.entries, (("HANS MEIER E K", "Sonstiges"),))
        for text in ("Kartenzahlung HANS MEIER E.K. Stadt", "REWE Markt", "..."):
            with self.subTest(text=text):
                self.assertEqual(classify(text, prepared), classify(text, rules))


class _FakePage:
    """Stands in for a pdfplumber page: records the x_tolerance used."""

    def __init__(self, text: str) -> None:
        self.chars = [{"text": ch} for ch in text]
        self.tolerance: float | None = None

    def extract_text(self, x_tolerance: float = 3) -> str:
        self.tolerance = x_tolerance
        return "text"


class PdfExtractionTest(unittest.TestCase):
    def test_embedded_cmap_is_parsed(self) -> None:
        # Encoding CMap as embedded by comdirect (1-byte identity mapping)
        data = (
            b"/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
            b"/CMapName /cmap def\n1 begincodespacerange\n<00> <FF>\n"
            b"endcodespacerange\n1 begincidrange\n<00> <FF> 0\nendcidrange\n"
            b"endcmap\n"
        )
        cmap = _parse_embedded_cmap(data)
        self.assertEqual(list(cmap.decode(b"\x00\x41\xff")), [0, 0x41, 0xFF])
        two_byte = _parse_embedded_cmap(
            b"begincidchar\n<0102> 7\nendcidchar\n"
        )
        self.assertEqual(list(two_byte.decode(b"\x01\x02")), [7])

    def test_embedded_cmap_ignores_oversized_ranges(self) -> None:
        cmap = _parse_embedded_cmap(
            b"begincidrange\n<00000000> <FFFFFFFF> 0\nendcidrange\n"
        )
        self.assertFalse(cmap.code2cid)

    def test_embedded_cmap_with_too_many_codes_is_rejected(self) -> None:
        # Many full 2-byte ranges: each one is allowed, together far too many.
        data = b"begincidrange\n" + b"<0000> <FFFF> 0\n" * 50 + b"endcidrange\n"
        with self.assertRaises(_CMapTooLarge):
            _parse_embedded_cmap(data)
        chars = b"begincidchar\n" + b"<41> 1\n" * 70_000 + b"endcidchar\n"
        with self.assertRaises(_CMapTooLarge):
            _parse_embedded_cmap(chars)

    def test_embedded_cmap_stream_too_long_is_rejected(self) -> None:
        with self.assertRaises(_CMapTooLarge):
            _parse_embedded_cmap(b" " * 2_000_000)

    def _hook(self, cmap, encoding):  # type: ignore[no-untyped-def]
        """Wrapped hook whose pdfminer original returns ``cmap``."""
        hook = _wrap_get_cmap_from_spec(lambda self, spec, strict: cmap)
        return hook(None, {"Encoding": encoding}, False)

    @staticmethod
    def _stream(data: bytes):  # type: ignore[no-untyped-def]
        from pdfminer.pdftypes import PDFStream

        return PDFStream({}, data)

    def test_hook_reads_embedded_cmap_for_empty_cmap(self) -> None:
        from pdfminer.cmapdb import CMap

        result = self._hook(
            CMap(), self._stream(b"begincidchar\n<41> 5\nendcidchar\n")
        )
        self.assertEqual(list(result.decode(b"A")), [5])

    def test_hook_keeps_known_and_non_empty_cmaps(self) -> None:
        from pdfminer.cmapdb import CMap, IdentityCMap

        stream = self._stream(b"begincidchar\n<41> 5\nendcidchar\n")
        identity = IdentityCMap(WMode=0)
        self.assertIs(self._hook(identity, stream), identity)
        known = CMap()
        known.code2cid[65] = 9
        self.assertIs(self._hook(known, stream), known)

    def test_hook_falls_back_on_oversized_or_broken_cmap(self) -> None:
        from pdfminer.cmapdb import CMap

        empty = CMap()
        huge = self._stream(
            b"begincidrange\n" + b"<0000> <FFFF> 0\n" * 50 + b"endcidrange\n"
        )
        self.assertIs(self._hook(empty, huge), empty)
        self.assertIs(self._hook(empty, "/Identity-H"), empty)

        class BrokenSpec:
            def get(self, key):  # type: ignore[no-untyped-def]
                raise ValueError("broken reference")

        hook = _wrap_get_cmap_from_spec(lambda self, spec, strict: empty)
        self.assertIs(hook(None, BrokenSpec(), False), empty)

    def test_patch_without_hook_falls_back(self) -> None:
        class FontWithoutHook:
            pass

        fake_module = type("pdffont", (), {"PDFCIDFont": FontWithoutHook})
        with self.assertLogs("yousplit.bankstatement", "WARNING"):
            self.assertFalse(_patch_cid_font(fake_module))
        self.assertFalse(hasattr(FontWithoutHook, "get_cmap_from_spec"))

    def test_patch_replaces_existing_hook(self) -> None:
        class Font:
            def get_cmap_from_spec(self, spec, strict):  # type: ignore[no-untyped-def]
                return "original"

        fake_module = type("pdffont", (), {"PDFCIDFont": Font})
        self.assertTrue(_patch_cid_font(fake_module))
        # Non-CMap results of the original pass through unchanged.
        self.assertEqual(Font().get_cmap_from_spec({}, False), "original")

    def test_tighter_word_gap_only_without_space_glyphs(self) -> None:
        spaceless = _FakePage("LidlsagtDanke" * 20)
        _page_text(spaceless)
        self.assertLess(spaceless.tolerance, 3)
        normal = _FakePage("Lidl sagt Danke " * 20)
        _page_text(normal)
        self.assertEqual(normal.tolerance, 3)


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

    def test_anzeigename_hinter_gleichheitszeichen(self) -> None:
        entries = parse_merchant_lines(
            ["YAZICI EINZELHANDELS = Rewe   # Franchise", "*BAECKEREI"]
        )
        self.assertEqual(
            [(e.keyword, e.substring, e.display) for e in entries],
            [("YAZICI EINZELHANDELS", False, "Rewe"), ("BAECKEREI", True, None)],
        )

    def test_mitgelieferte_datei_ist_sauber(self) -> None:
        entries = load_food_merchants()
        self.assertGreater(len(entries), 200)
        # zu kurze Stichwoerter waeren Fehlalarm-Quellen (ausser bewusst bekannte)
        short = [e.keyword for e in entries if len(e.keyword) < 3]
        self.assertEqual(short, [], short)


if __name__ == "__main__":
    unittest.main()
