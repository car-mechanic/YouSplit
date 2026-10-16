# YouSplit

Gemeinsame Ausgaben erfassen und sehen, wer wem wie viel schuldet.

## Grundgedanke

YouSplit soll auf möglichst einfache Weise zeigen, **wer wie viel für Lebensmittel
im Monat ausgibt** und **wie hoch die gemeinsamen Ausgaben sind**. Kein Konto,
keine Cloud: eine Liste anlegen, Link teilen, Ausgaben eintragen.

## Funktionen

- Listen ohne Benutzerkonto, geteilt per Link
- Ausgaben mit Zahler, Kategorie und Datum
- Flexible Aufteilung: gleichmäßig, Prozent, Beträge oder Anteile
- Kassensturz: wer wem wie viel zahlen muss
- Statistiken nach Kategorie und Person
- Fremdwährungen mit automatischem Umrechnungskurs in EUR

## Datenschutz

Alle eingetragenen Daten liegen ausschließlich in der PostgreSQL-Datenbank auf
dem Gerät, auf dem YouSplit läuft. Die einzige ausgehende Verbindung ist der
Kursabruf bei [Frankfurter](https://www.frankfurter.app) für Ausgaben in
Fremdwährung; dabei wird nur der Währungscode übertragen (z. B. `USD`).

**Wichtig:** Wer den Link einer Liste kennt, kann sie sehen und bearbeiten.
Links also nur an Personen geben, die mitrechnen sollen.

## Betrieb

### Home Assistant (Add-on)

1. *Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories*
2. `https://github.com/car-mechanic/YouSplit` hinzufügen
3. **YouSplit** installieren, starten und über `http://<HA-IP>:8099` öffnen

Die Daten sind Teil der Home-Assistant-Backups. Details: [`yousplit/DOCS.md`](yousplit/DOCS.md).

### Einzelner Container (ohne Home Assistant)

Dasselbe Image wie das Add-on, mit Datenbank und Oberfläche in einem Container:

```bash
docker run -d --init --name yousplit -p 8099:8099 \
  -v yousplit-data:/data --restart unless-stopped \
  ghcr.io/car-mechanic/yousplit-addon-amd64
```

Auf ARM-Geräten (z. B. Raspberry Pi 4/5) `yousplit-addon-aarch64` verwenden.
Danach `http://<IP>:8099` öffnen. Die Daten liegen im Volume `yousplit-data`.
`--init` ist nötig, damit die Datenbank beim Stoppen sauber herunterfährt.

Selbst bauen statt herunterladen:

```bash
docker build -f Dockerfile.addon -t yousplit .
```

### Entwicklung (Docker Compose)

Frontend, Backend und Datenbank als getrennte Container, mit Hot-Reload:

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- API-Doku: http://localhost:8000/docs

## Technik

React + TypeScript (Vite, Tailwind) · FastAPI · PostgreSQL

## Lizenz

[GNU AGPL-3.0](LICENSE). Wer YouSplit verändert und als Dienst anbietet, muss
den geänderten Quellcode ebenfalls veröffentlichen.
