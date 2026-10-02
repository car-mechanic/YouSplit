# CLAUDE.md

> Diese Datei wird von Claude Code automatisch geladen. Sie hält sich bewusst
> kurz und verweist auf die ausführliche Projektdokumentation.

## 📖 Zuerst lesen: `AI_CONTEXT.md`

**Die maßgebliche Wissens- und Richtlinienquelle für dieses Projekt ist
[`AI_CONTEXT.md`](./AI_CONTEXT.md).** Dort stehen:

- **Projekt-Übersicht & Tech-Stack** (React/TS-Frontend, FastAPI-Backend,
  PostgreSQL, lokales Ollama `qwen2.5vl:3b`, Docker Compose)
- **Architektur-Richtlinien** (Zusammenspiel der Services, Datenmodell,
  Endpunkte, Kassenbon-Scan-Ablauf, Kassensturz-Logik)
- **Coding-Standards** (Clean Code, **deutsche Kommentare**, Modulstruktur)
- **Aktueller Status & Roadmap** inkl. bekannter Tech-Debt

Bitte `AI_CONTEXT.md` zu Beginn jeder Sitzung lesen und **nach relevanten
Änderungen fortschreiben** (neue Endpunkte, geänderte Architektur, erledigte
Roadmap-Punkte). Sie ist das dauerhafte Gedächtnis des Projekts.

## Schnellstart

```bash
docker compose up --build
# Erststart: einmalig das Vision-Modell laden
docker compose exec ollama ollama pull qwen2.5vl:3b
```

Frontend: http://localhost:5173 · Backend/Docs: http://localhost:8000/docs
