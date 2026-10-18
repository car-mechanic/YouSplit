# YouSplit

Ausgaben erfassen, per Kontoauszug-Import aufnehmen und den Kassensturz berechnen.

## Installation

1. Home Assistant → *Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories*
2. `https://github.com/car-mechanic/YouSplit` hinzufügen
3. **YouSplit** installieren und starten, danach über *Benutzeroberfläche öffnen*
   aufrufen. Mit *In Seitenleiste anzeigen* erscheint YouSplit in der Seitenleiste.

## Daten

Die Datenbank (PostgreSQL, läuft im Add-on) liegt in `/data/postgres` und ist Teil der
Home-Assistant-Backups. Für ein konsistentes Backup hält Home Assistant das
Add-on währenddessen kurz an (`backup: cold`).

## Mehrere Geräte und Benutzer

Über Home Assistant (Seitenleiste bzw. *Benutzeroberfläche öffnen*) erkennt
YouSplit den angemeldeten HA-Benutzer. Dann gilt:

- **Meine Listen** auf der Startseite kommen vom Server: jede Liste, die du
  geöffnet hast, und jede, in der du als Person verknüpft bist. Handy, PC und
  Tablet zeigen dieselben Listen.
- **Personen aus Home Assistant:** Beim Festlegen der Personen erscheinen die
  HA-Benutzer zum Antippen. Verknüpfte Personen sehen die Liste automatisch und
  werden beim Eintragen als Zahler vorgeschlagen.
- **Live:** Eine offene Liste lädt alle 10 Sekunden nach und sofort, wenn du in
  den Tab zurückkehrst.

Alle HA-Benutzer sehen YouSplit in der Seitenleiste (`panel_admin: false`).
Für die Benutzerliste braucht das Add-on Zugriff auf die Home-Assistant-API
(`homeassistant_api`). Es liest damit nur die Benutzer (Name und ID).

Über Port 8099 (Share-Links) gibt es keinen HA-Benutzer: dort merkt sich jeder
Browser seine Listen selbst, wie bisher.

## Teilen

Listen werden per Link geteilt (wer den Link kennt, sieht die Liste). Über
Ingress liegt die Oberfläche hinter dem Home-Assistant-Login. Für Share-Links
bleibt deshalb Port 8099 direkt erreichbar. Für den Zugriff von außen z. B.
einen Reverse-Proxy oder Cloudflare-Tunnel auf Port 8099 setzen und dessen
Adresse als `public_url` eintragen.

## Optionen

- `log_level`: DEBUG, INFO, WARNING oder ERROR
- `public_url` (optional): öffentliche Adresse von Port 8099, z. B.
  `https://split.example.org`. „Link kopieren“ nutzt diese Adresse. Ohne
  `public_url` kopiert die App die aktuelle Adresse; im Ingress ist das die
  Home-Assistant-Adresse, die nur mit HA-Login funktioniert.
