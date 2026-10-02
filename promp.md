# Projektübersicht: "YouSplit AI" (Arbeitstitel)
Eine Web-App ähnlich wie Tricount, mit der Nutzer gemeinsame Ausgaben tracken und Kassenbons per lokaler KI analysieren können.

## Tech-Stack
- **Frontend:** React (Vite) mit Tailwind CSS
- **Backend:** Python, FastAPI
- **Datenbank:** PostgreSQL (via SQLAlchemy oder SQLModel)
- **KI / OCR:** Ollama (lokal, z.B. mit Llama-3-Vision) – angesprochen über die OpenAI-kompatible Schnittstelle.
- **Infrastruktur:** Docker Compose (Frontend, Backend, DB, Ollama in separaten Containern)
- **CI/CD:** GitHub Actions -> GitHub Container Registry -> Watchtower auf dem Homeserver.

## Produkt-Regeln (MVP - Minimum Viable Product)
1. **Authentifizierung:** KEINE Benutzerkonten für den Start. Listen werden erstellt und erhalten eine eindeutige UUID. Jeder, der den Link hat (`/list/{uuid}`), kann die Liste sehen und bearbeiten.
2. **Kostenaufteilung:** Standardmäßig 50/50. Beim Eintragen einer Ausgabe gibt es einen Slider/Regler, um die Gewichtung (z.B. 70/30) für den Gesamtbetrag anzupassen. 
3. **Kassenbon-Analyse:**
   - User lädt ein Bild hoch.
   - Backend schickt das Bild an die lokale Ollama-Instanz.
   - KI liest den Gesamtbetrag und kategorisiert die Ausgaben (z.B. Lebensmittel, Kosmetik).
   - Die Analyse nach Kategorien wird in der Liste als Metadaten gespeichert (für spätere Statistiken).
   - *WICHTIG:* Das Aufteilen einzelner Artikel auf verschiedene Personen ist ausgenommen (Backlog für später). Es wird nur der Gesamtbetrag aufgeteilt.
   - Wenn kein Bon hochgeladen wird oder die KI scheitert, ist die Kategorie "Unknown/Manuell".

## Code-Style & Architektur
- Monorepo-Struktur: `/frontend` und `/backend` im selben Hauptverzeichnis.
- Backend: API-Routen sauber trennen (z.B. `routers/lists.py`, `routers/expenses.py`).
- Nutze Type-Hints in Python und TypeScript im Frontend.
- Bevor du (Claude) Code schreibst, denke Schritt für Schritt nach und halte dich strikt an diese Vorgaben.