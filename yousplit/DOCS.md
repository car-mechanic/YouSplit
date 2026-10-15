# YouSplit

Ausgaben erfassen, per Kontoauszug-Import aufnehmen und den Kassensturz berechnen.

## Installation

1. Home Assistant → *Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories*
2. `https://github.com/car-mechanic/YouSplit` hinzufügen
3. **YouSplit** installieren und starten, danach über `http://<HA-IP>:8099` öffnen.

## Daten

Die Datenbank (SQLite) liegt in `/data/yousplit.db` und ist Teil der
Home-Assistant-Backups.

## Teilen

Listen werden per Link geteilt (wer den Link kennt, sieht die Liste). Der Port
8099 ist deshalb bewusst direkt erreichbar und nicht über Ingress eingebunden.
Für den Zugriff von außen z. B. einen Reverse-Proxy oder Cloudflare-Tunnel auf
Port 8099 setzen.

## Optionen

- `log_level`: DEBUG, INFO, WARNING oder ERROR
