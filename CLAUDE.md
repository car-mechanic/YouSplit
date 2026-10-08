# CLAUDE.md

> Diese Datei wird von Claude Code automatisch geladen. Sie hält sich bewusst
> kurz und verweist auf die ausführliche Projektdokumentation.

## 📖 Zuerst lesen: `AI_CONTEXT.md`

**Die maßgebliche Wissens- und Richtlinienquelle für dieses Projekt ist
[`AI_CONTEXT.md`](./AI_CONTEXT.md).** Dort stehen:

- **Projekt-Übersicht & Tech-Stack** (React/TS-Frontend, FastAPI-Backend,
  PostgreSQL, Docker Compose; Ollama/Kassenbon-Scan seit 2026-10-08 entfernt)
- **Architektur-Richtlinien** (Zusammenspiel der Services, Datenmodell,
  Endpunkte, Kassensturz-Logik; alter Scan-Ablauf nur noch als Referenz)
- **Coding-Standards** (Clean Code, **deutsche Kommentare**, Modulstruktur)
- **Aktueller Status & Roadmap** inkl. bekannter Tech-Debt

Bitte `AI_CONTEXT.md` zu Beginn jeder Sitzung lesen und **nach relevanten
Änderungen fortschreiben** (neue Endpunkte, geänderte Architektur, erledigte
Roadmap-Punkte). Sie ist das dauerhafte Gedächtnis des Projekts.

## Schnellstart

```bash
docker compose up --build
# Einmalig nach der Ollama-Entfernung: verwaisten Container aufräumen
docker compose up --build --remove-orphans
```

Frontend: http://localhost:5173 · Backend/Docs: http://localhost:8000/docs

## 🔀 Git-Workflow

Nach jeder abgeschlossenen Änderung **immer ohne Rückfrage** committen und
nach `origin/main` pushen (`git add -A && git commit && git push`).
Commit-Nachrichten auf Deutsch, kurz und aussagekräftig. Vorher prüfen, dass
keine Geheimnisse (`.env`, Tokens) im Commit landen.
