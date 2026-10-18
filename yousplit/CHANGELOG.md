# Changelog

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
