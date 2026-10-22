# CLAUDE.md

> Diese Datei wird von Claude Code automatisch geladen. Offene Aufgaben und
> Tech-Debt stehen als Issues auf GitHub (`car-mechanic/YouSplit`). Die frühere
> ausführliche Projektdoku `AI_CONTEXT.md` liegt nur noch in der Git-Historie.

## Projekt

Gemeinsame Ausgaben je Liste erfassen (ohne Konto, Teilen per Link),
Kontoauszug-Import für Lebensmittel, Kassensturz „wer zahlt wem wie viel“.

- **Frontend:** React + TypeScript (Vite, Tailwind, `lucide-react`), `frontend/`
- **Backend:** FastAPI + SQLAlchemy 2.0 + Pydantic v2, `backend/`
- **DB:** PostgreSQL. Schema per `create_all`, neue Spalten über
  `database.ensure_schema_updates()` (kein Alembic).
- **Betrieb:** Docker Compose (Entwicklung) oder Home-Assistant-Add-on
  (`Dockerfile.addon`, `yousplit/`), ein Container mit Postgres, Backend und
  Frontend-Build. Images baut `.github/workflows/addon-image.yml` nach GHCR.

## Schnellstart

```bash
docker compose up --build
```

Frontend: http://localhost:5173 · Backend/Docs: http://localhost:8000/docs

Tests:

```bash
cd backend && python -m unittest discover -s tests
cd frontend && npm test && npm run lint && npm run build
```

## Konventionen

- **Kommentare und Docstrings auf Deutsch**, sie erklären das Warum.
  Bezeichner bleiben englisch.
- **Eine Wahrheit:** TS-Typen in `frontend/src/api.ts` spiegeln die
  Pydantic-Schemas. Ändert sich ein Schema, beide Seiten anpassen.
- **Netzwerkaufrufe nur über `api.ts`**, Fehler als `ApiError`, UI-Meldungen
  über `withReason(…)`.
- **Beträge mit `parseAmount` (`format.ts`) lesen**, nie mit `parseFloat`.
- **Personen über `collectParticipants`**, Kategorien aus `categories.ts`.
- **Router dünn halten:** Fachlogik in eigene Module (`settlement.py`,
  `splits.py`, `bank_statement.py`, …).
- **Logging** über `logging.getLogger("yousplit.<bereich>")`, kein `print`.
- **Neue Logik bringt ihren Test mit** (Backend `unittest`, Frontend vitest
  für reine Module).
- **Tests über Subagenten:** Nach Änderungen in `backend/` den Agenten
  `backend-tester`, nach Änderungen in `frontend/` den `frontend-tester`
  verwenden (Definitionen in `.claude/agents/`). Bei beidem parallel starten.
  So bleibt die lange Testausgabe aus dem Hauptkontext.
- **Neues Release des Add-ons:** `version` in `yousplit/config.yaml` erhöhen und
  `yousplit/CHANGELOG.md` ergänzen. Ohne neue Version bietet HA kein Update an.

## 🔀 Git-Workflow

Nach jeder abgeschlossenen Änderung **immer ohne Rückfrage** committen und
nach `origin/main` pushen (`git add -A && git commit && git push`).
Commit-Nachrichten, READMEs und sonstige Repo-Doku auf Englisch, kurz und
aussagekräftig (Code-Kommentare bleiben deutsch, siehe Konventionen). Vorher prüfen, dass
keine Geheimnisse (`.env`, Tokens) im Commit landen.

## Lessons learned

- uvicorn (≥ 0.29) löst SIGTERM nach dem Shutdown erneut aus. Unter tini (Add-on `init: true`) tötet das Python, bevor `finally` läuft. Deshalb setzt `yousplit/run.py` einen eigenen SIGTERM-Handler. Stopp-Tests immer mit `docker run --init`, sonst ist Python PID 1 und ignoriert das Signal.
- Das Frontend nutzt nur relative Pfade (Vite `base: './'`, `API_BASE_URL = "api"`, Router-`basename` aus `<base href>`). Grund: HA-Ingress liefert die App unter `/api/hassio_ingress/<token>/` aus. Ein neuer absoluter Pfad bricht den Ingress.
- GHCR-Pakete gehören zu dem Repo, dessen Action sie angelegt hat. Nach einem Repo-Wechsel scheitert der Push mit `denied: write_package`, bis das neue Repo in den Package-Settings unter „Manage Actions access“ Write bekommt.
- `requirements.txt` pinnt alle direkten Abhängigkeiten. Ein ungepinnter Neubau zog einmal SQLAlchemy 2.1, das `psycopg` (v3) statt `psycopg2` wählte. Seitdem setzt `database.py` `postgresql+psycopg2://` explizit.
- Die Startseite kannte Listen nur aus dem localStorage. Am PC fehlten deshalb die Einträge vom Handy (vermutlich je Gerät eine eigene Liste mit gleichem Titel). Über Ingress liegen „Meine Listen“ jetzt auf dem Server (`list_bookmarks`, `member_users`). Neue Gerätezustände nicht wieder in den localStorage legen.
- Ingress-Benutzer-Header (`X-Remote-User-*`) nur von `172.30.32.2` glauben (`ha_identity.py`). Port 8099 ist offen, dort kann jeder die Header setzen. Starlette dekodiert Header als Latin-1, der Supervisor schickt UTF-8: umkodieren, sonst wird aus „Jörg“ „JÃ¶rg“.
- Die HA-Benutzerliste kommt per Core-Websocket `config/auth/list` (`homeassistant_api`). Supervisor-`/auth/list` bräuchte `hassio_role: admin` und liefert keine IDs. Die Add-on-Doku liegt inzwischen unter contributors.home-assistant.io/apps (Add-ons heißen dort „Apps“).
- Der Vite-Watcher im Compose-Container erkennt Änderungen über den Windows-Bind-Mount nicht zuverlässig. Dann `docker compose restart frontend`.
