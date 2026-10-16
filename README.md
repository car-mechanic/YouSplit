# YouSplit

🇬🇧 **English version: [README.en.md](README.en.md)**

Gemeinsame Ausgaben eintragen und auf einen Blick sehen, wer wem wie viel schuldet.

## Worum geht's?

Die Idee hinter YouSplit ist ganz einfach: Man will **ohne viel Aufwand sehen,
wer wie viel im Monat für Lebensmittel ausgibt** und **wie hoch die gemeinsamen
Ausgaben sind**.

Dafür braucht es kein Benutzerkonto und keine Cloud. Du legst eine Liste an,
teilst den Link mit deinen Mitbewohnern oder deiner Familie, und alle tragen
dort ihre Ausgaben ein. YouSplit rechnet aus, wer wem noch Geld schuldet.

## So geht's am einfachsten: einmal im Monat den Kontoauszug hochladen

Ausgaben einzeln abzutippen ist mühsam. Schneller geht es so:

1. **Jede Person lädt einmal im Monat ihren Kontoauszug hoch** (als PDF aus dem
   Online-Banking).
2. **YouSplit erkennt die Lebensmitteleinkäufe automatisch** und hakt sie schon an.
3. **Kurz drüberschauen:** Stimmt alles? Fehlt ein Einkauf, kannst du ihn
   nachträglich anhaken. Gehört einer nicht dazu, nimmst du den Haken raus.
4. Auswählen, wer bezahlt hat, und auf **„Buchungen anlegen“** klicken. Fertig.
5. **Den Kontoauszug danach wieder löschen.** YouSplit speichert das PDF
   sowieso nicht. Übernommen werden nur die angehakten Einkäufe mit Datum,
   Betrag und Geschäft.

**Warum das sicher ist:** YouSplit läuft auf deinem eigenen Gerät oder Server.
Dein Kontoauszug wird dort ausgewertet und geht an niemanden sonst. Deine
sensiblen Bankdaten landen also nicht bei irgendwelchen Drittanbietern.

Gut zu wissen:

- Es funktionieren PDFs, in denen man den Text markieren kann, so wie sie
  das Online-Banking liefert. Eingescannte Papier-Auszüge gehen nicht.
- Der Import ist auf Kontoauszüge deutscher Banken ausgelegt.
- Ausgaben, die schon in der Liste stehen, erkennt YouSplit und hakt sie
  nicht doppelt an.
- Drogerien wie dm oder Rossmann zählen als Lebensmittel, weil man dort
  oft auch Essen kauft.

### Welche Geschäfte erkannt werden

Die Geschäfte stehen in der Datei
[`backend/food_merchants.txt`](backend/food_merchants.txt). Ich habe sie von
Hand zusammengestellt. Der Schwerpunkt liegt auf **bekannten Supermärkten,
Discountern, Bäckern und Metzgern aus Deutschland und Europa**. Dazu kommen
große Ketten aus anderen Ländern.

Die Liste ist bestimmt nicht vollständig. Fehlt dein Markt, kannst du ihn
einfach selbst eintragen. Wie das geht, steht oben in der Datei.

## Was YouSplit kann

- Listen ohne Benutzerkonto, geteilt per Link
- Ausgaben mit Zahler, Kategorie und Datum
- Kontoauszug-Import für Lebensmitteleinkäufe
- Kosten frei aufteilen: gleichmäßig, in Prozent, nach Beträgen oder Anteilen
- Kassensturz: wer wem wie viel zahlen muss
- Statistiken nach Kategorie und Person
- Fremdwährungen, automatisch in Euro umgerechnet

## Deine Daten

**Alles, was du einträgst, bleibt auf dem Gerät, auf dem YouSplit läuft.**
Es gibt keine Cloud, keine Werbung und keine Statistik-Dienste.

Nur bei Ausgaben in einer Fremdwährung fragt YouSplit den aktuellen
Wechselkurs bei [Frankfurter](https://www.frankfurter.app) ab. Dabei wird nur
die Währung übertragen (zum Beispiel „USD“), keine Beträge und keine Namen.

**Wichtig:** Wer den Link zu einer Liste hat, kann sie ansehen und bearbeiten.
Gib den Link also nur an Leute, die mitrechnen sollen.

## Installation

### In Home Assistant (Add-on)

1. In Home Assistant: *Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories*
2. Diese Adresse hinzufügen: `https://github.com/car-mechanic/YouSplit`
3. **YouSplit** installieren und starten
4. Im Browser `http://<IP-von-Home-Assistant>:8099` öffnen

Deine Daten sind automatisch in den Home-Assistant-Backups enthalten.
Mehr dazu: [`yousplit/DOCS.md`](yousplit/DOCS.md)

### Als einzelner Docker-Container (ohne Home Assistant)

Ein Container enthält alles: Datenbank und Oberfläche.

```bash
docker run -d --init --name yousplit -p 8099:8099 \
  -v yousplit-data:/data --restart unless-stopped \
  ghcr.io/car-mechanic/yousplit-addon-amd64
```

- Auf einem Raspberry Pi 4 oder 5 statt `amd64` einfach `aarch64` nehmen.
- Danach im Browser `http://<IP-des-Geräts>:8099` öffnen.
- Deine Daten liegen im Docker-Volume `yousplit-data`.
- `--init` bitte nicht weglassen. Sonst wird die Datenbank beim Stoppen nicht
  sauber beendet.

Lieber selbst bauen? Das geht so:

```bash
docker build -f Dockerfile.addon -t yousplit .
```

### Zum Entwickeln (Docker Compose)

Frontend, Backend und Datenbank laufen in getrennten Containern. Änderungen
am Code sind sofort sichtbar.

```bash
docker compose up --build
```

- Oberfläche: http://localhost:5173
- API-Dokumentation: http://localhost:8000/docs

## Technik

React + TypeScript (Vite, Tailwind) · FastAPI · PostgreSQL

## Lizenz

[GNU AGPL-3.0](LICENSE). Du darfst YouSplit frei nutzen, verändern und
weitergeben. Wer eine veränderte Version als Online-Dienst anbietet, muss
seinen geänderten Quellcode ebenfalls veröffentlichen.
