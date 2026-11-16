# Changelog

## 1.6.0
- Bank statement import: remembered merchants. For an unrecognized or
  overridden booking, choose "Remember merchant", confirm or edit the
  suggested keyword and mark it as groceries or not groceries. The rule is
  stored per list, takes precedence over the built-in merchant list and the
  heuristic, and matches whole words only. The preview is reclassified
  immediately. Rules can be viewed and deleted under "Remembered merchants".

## 1.5.0
- Bank statement import recognizes more grocery merchants: the abbreviation EDK
  for Edeka, more Edeka and Rewe name formats, regional Edeka companies and
  large independent retailers.
- Owner-run markets that appear under their company name are now detected too:
  a legal form (e.K., oHG, KG, ...) plus a grocery word such as "Markt" or
  "Lebensmittel". DIY, electronics, furniture, restaurants and similar
  businesses are excluded.

## 1.4.0
- Neu: Drei-Punkte-Menü an jeder Liste in der Übersicht mit „Umbenennen“ und
  „Löschen“. Löschen entfernt die Liste samt Ausgaben für alle Personen.
- Der Darkmode-Schalter sitzt jetzt oben rechts, „← Übersicht“ oben links.
- In Home Assistant ist „Link teilen“ ausgegraut: Listen teilst du dort, indem
  du Benutzer als Personen einträgst.
- Neuer Text auf der Startseite.

## 1.3.0
- Neu: Darkmode. Der Schalter (Mond/Sonne) sitzt oben links; die Wahl wird je
  Gerät gemerkt, beim ersten Besuch gilt die Systemeinstellung.

## 1.2.0
- Behoben: Listen vom Handy fehlten am PC. Die Startseite kannte nur die Listen,
  die auf dem jeweiligen Gerät geöffnet wurden. Über Home Assistant stehen sie
  jetzt als „Meine Listen“ auf dem Server und sind auf allen Geräten gleich.
  Bisher nur lokal gemerkte Listen werden beim ersten Aufruf übernommen.
- Personen lassen sich direkt aus den Home-Assistant-Benutzern auswählen.
  Verknüpfte Benutzer sehen die Liste automatisch und werden als Zahler
  vorgeschlagen. „Wer bist du?“ im Tutorial verknüpft dein eigenes Konto.
- Offene Listen aktualisieren sich selbst (alle 10 s und beim Zurückkehren in
  den Tab): Einträge anderer Geräte erscheinen ohne Neuladen.
- YouSplit steht jetzt allen HA-Benutzern in der Seitenleiste zur Verfügung,
  nicht nur Administratoren (`panel_admin: false`).
- Neue Berechtigung `homeassistant_api`: nötig für die Benutzerliste.

## 1.1.0
- Oberfläche über Ingress direkt in Home Assistant, optional in der Seitenleiste
  (Add-on-Info → „In Seitenleiste anzeigen“).
- Neue Option `public_url`: öffentliche Adresse für Share-Links.

## 1.0.0
- Erste Version als Home-Assistant-Add-on (Frontend + Backend in einem Container, PostgreSQL).
