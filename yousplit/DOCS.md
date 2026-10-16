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
