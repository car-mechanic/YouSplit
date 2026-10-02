# AI_CONTEXT.md — Projekt-Gedächtnis für YouSplit

> **Zweck dieser Datei:** Zentrale, dauerhafte Wissens- und Richtlinienquelle für
> KI-Agenten (und Menschen), die an YouSplit arbeiten. Sie beschreibt _was_ das
> Projekt ist, _wie_ es aufgebaut ist und _nach welchen Regeln_ Code entsteht.
>
> **Für Agenten:** Diese Datei zu Beginn jeder Sitzung lesen. Nach relevanten
> Änderungen (neue Endpunkte, geänderte Architektur, erledigte Roadmap-Punkte)
> **diese Datei mit aktualisieren** — sie ist das Gedächtnis, nicht der Chat.
> Sie ersetzt keinen Blick in den Code; im Zweifel gilt der Code.

---

## 1. Projekt-Übersicht & Tech-Stack

**YouSplit** ist eine App zum Aufteilen gemeinsamer Ausgaben ("Split-App") mit
**Kassenbon-Scan**: Man fotografiert einen Bon, eine lokale Vision-KI liest
Titel, Betrag und Kategorie automatisch aus, und die App rechnet aus, wer wem
wie viel schuldet ("Kassensturz").

Kernidee: **Privacy-first & lokal** — die OCR/KI läuft über ein lokales
Ollama-Modell, es verlässt kein Bon-Bild das eigene System / den eigenen Server.

### Tech-Stack

| Schicht        | Technologie                                                                 |
| -------------- | --------------------------------------------------------------------------- |
| **Frontend**   | React 19 + **TypeScript**, Vite, **Tailwind CSS v4** (via `@tailwindcss/vite`), `react-router-dom`, `lucide-react`, **`recharts`** (Charts, Roadmap 2.0 #2) |
| **Backend**    | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Pillow (Bildverkleinerung), httpx |
| **Datenbank**  | PostgreSQL 17 (`postgres:17-alpine`)                                          |
| **KI / OCR**   | Lokales **Ollama**, Modell **`qwen2.5vl:3b`** (Vision), angesprochen über `/api/chat` |
| **Wechselkurse** | **Frankfurter-API** (Key-los, `frankfurter.app` → `.dev`) via `httpx` — Multi-Currency (Roadmap 2.0 #3) |
| **Orchestrierung** | Docker Compose (4 Services: `frontend`, `backend`, `db`, `ollama`)       |

> ⚠️ **Präzisierung zur ursprünglichen Beschreibung:** Es sind faktisch **vier**
> Compose-Services (nicht drei). Die "DB" ist konkret PostgreSQL. Das Frontend
> ist **TypeScript**, nicht reines JS.

### Verzeichnisstruktur (Ist-Zustand)

```
YouSplit/
├─ docker-compose.yml          # Orchestriert alle 4 Services (Ollama = CPU-Default)
├─ docker-compose.gpu.yml      # Optionales GPU-Override für Ollama (NVIDIA)
├─ .env                        # COMPOSE_FILE-Schalter: CPU (Default) ↔ GPU
├─ AI_CONTEXT.md               # Diese Datei
├─ promp.md                    # Ursprüngliche Projekt-Spezifikation/Notizen
├─ backend/
│  ├─ Dockerfile
│  ├─ requirements.txt
│  ├─ main.py                  # FastAPI-App, CORS, Lifespan (Tabellen-Setup, verwaiste Jobs, Modell-Auto-Pull), Router-Registrierung
│  ├─ logging_setup.py         # Zentrales logging (Format, LOG_LEVEL, Polling-Filter im Access-Log) — seit 2026-09-25
│  ├─ database.py              # Engine, SessionLocal, Base, get_db()-Dependency
│  ├─ models.py                # SQLAlchemy-Modelle: SharedList, Expense, CategoryRule (Epic 4.0), ReceiptJob (2026-09-25)
│  ├─ receipt_jobs.py          # Status-Wechsel der Bon-Scan-Jobs (eigene Sessions) + Aufräumen nach Neustart
│  ├─ schemas.py               # Pydantic-Schemas (Request/Response) + ReceiptAnalysis + Settlement + CategoryRule
│  ├─ ollama_client.py         # Bildvorbereitung + Ollama-Aufruf + Validierung + Modell-Check/Auto-Pull (ensure_model)
│  ├─ currency.py              # Wechselkurs-Abruf (Frankfurter-API) — Multi-Currency
│  ├─ settlement.py            # Kassensturz für N Personen (reine Logik, testbar, in EUR); collect_persons
│  ├─ splits.py                # fair_split(): gleichmäßige Aufteilung + 1-Cent-Rest (rein, testbar, Epic 4.0)
│  ├─ bank_statement.py        # Kontoauszug-Parser: PDF → Buchungen + Lebensmittel-Erkennung (rein, testbar, Epic 4.0 #3, 2026-10-02)
│  ├─ food_merchants.txt       # Händlerliste für die Lebensmittel-Erkennung — VON HAND ERWEITERBAR (~330 Einträge weltweit, 2026-10-02)
│  ├─ tests/test_bank_statement.py # unittest für den Parser (`python -m unittest discover -s tests`)
│  └─ routers/
│     └─ lists.py              # Alle Endpunkte; Bon-Upload jetzt asynchron (BackgroundTasks, Epic 4.0)
└─ frontend/
   ├─ Dockerfile
   ├─ vite.config.ts, tsconfig*.json, eslint.config.js
   └─ src/
      ├─ main.tsx              # Einstiegspunkt (Router-Mount)
      ├─ App.tsx               # Routen: "/" → Home, "/list/:id" → ListView
      ├─ api.ts                # API-Client-Funktionen + TS-Typen + DuplicateError + Währungslisten (spiegeln die Schemas)
      ├─ format.ts             # formatEuro() + formatMoney() + formatDate() (Intl, de-DE)
      ├─ splitMath.ts          # REINE Split-Berechnung (Locking, 1-Cent-Verteilung) — testbar (Roadmap 3.0 #3)
      ├─ recentLists.ts        # Zuletzt besuchte Listen im localStorage (Startseite, Roadmap 3.0 #1)
      ├─ payerStorage.ts       # localStorage-Schlüssel des gemerkten Zahlers je Liste (ExpenseForm + BankStatementView)
      ├─ useReceiptJobs.ts     # Hook: pollt Bon-Scan-Status, lädt Liste bei "done" neu (2026-09-25)
      ├─ pages/
      │  ├─ Home.tsx           # Startseite/Dashboard: CTA "Neue Liste" (Modal) + Grid zuletzt besuchter Listen (Roadmap 3.0 #1)
      │  └─ ListView.tsx       # Orchestrator: lädt Liste + Kassensturz, koordiniert Edit/Delete, merkt Besuch
      └─ components/
         ├─ ListHeader.tsx     # Kopf-Card (Titel, Summe, Teilen-Link)
         ├─ ListTabs.tsx       # Tab-Leiste: Ausgaben / Kassensturz / Statistiken / Kontoauszug (Epic 4.0 #3)
         ├─ StatisticsBoard.tsx # Charts (recharts): Kategorie-Donut + Ausgaben je Person (Roadmap 2.0 #2, in EUR)
         ├─ BankStatementView.tsx # Kontoauszug-Import (Epic 4.0 #3): Upload → Vorschau (Häkchen) → Import als Einzelausgaben
         ├─ AdvancedSplitter.tsx # Kostenaufteilung über ALLE Teilnehmer: 3 Modi (%/Betrag/Anteile), Locking (Roadmap 3.0 #3)
         ├─ CurrencySelect.tsx # Währungs-Dropdown: Hauptwährungen + "Mehr…" klappt EU-Währungen auf (Roadmap 3.0 #2)
         ├─ SettlementCard.tsx # Kassensturz-UI für N Personen (zeigt Settlement vom Backend)
         ├─ ExpenseForm.tsx    # "Ausgabe hinzufügen"-Feature (Formular, Zahler-Dropdown, Scan, Duplikat, Splitter)
         ├─ ReceiptJobsPanel.tsx # Status laufender/fehlgeschlagener Bon-Scans (Spinner bzw. Fehler + Verwerfen)
         ├─ ExpenseList.tsx    # Abschnitt "Bisherige Ausgaben" (Sortierung, Empty State)
         ├─ ExpenseListItem.tsx # Eine Ausgabe als Card (Meta, Datum, Betrag, Aktionen)
         ├─ DatePicker.tsx     # Eigener Kalender-Picker (emerald) fürs Ausgabendatum
         ├─ Modal.tsx          # Wiederverwendbare Modal-Hülle (Bottom-Sheet mobil, Dialog ab sm)
         ├─ ConfirmDialog.tsx  # Bestätigungsdialog (Duplikats-Warnung + Löschen)
         └─ EditExpenseModal.tsx # Formular-Modal zum Bearbeiten einer Ausgabe (inkl. DatePicker + Splitter)

> **Hinweis (2026-07-20, To-Do 3):** `balance.ts` (2-Personen-`calculateBalance`)
> und `BalanceCard.tsx` wurden durch den Backend-Settlement-Endpoint + die neue
> `SettlementCard.tsx` ersetzt und entfernt.
```

---

## 2. Architektur-Richtlinien

### 2.1 Zusammenspiel der Services

```
Browser (React/Vite :5173)
      │  fetch → http://localhost:8000/api/...
      ▼
FastAPI Backend (:8000)  ──SQLAlchemy──►  PostgreSQL (db:5432)
      │
      │  Bon-Bild als Base64 (POST /api/chat)
      ▼
Ollama (:11434, qwen2.5vl:3b)
```

- **Frontend → Backend:** Ausschließlich über `frontend/src/api.ts`. Kein
  direkter `fetch` in Komponenten — neue Endpunkte immer als Funktion in `api.ts`
  kapseln, inkl. passender TS-Typen. Basis-URL ist `http://localhost:8000/api`.
- **Backend → DB:** SQLAlchemy 2.0 (`Mapped`/`mapped_column`). Session-Zugriff
  **nur** über die `get_db()`-Dependency (`Depends(get_db)`), nie global.
  Tabellen werden aktuell beim App-Start via `Base.metadata.create_all` angelegt
  (noch **kein Alembic** — Migrationen sind Zukunft, siehe Roadmap/Tech-Debt).
- **Backend → Ollama:** Gekapselt in `ollama_client.py`. Kein anderer Code spricht
  direkt mit Ollama. Kommunikation über `httpx.AsyncClient`, Endpoint `/api/chat`
  mit `"format": "json"` und erhöhtem `num_ctx` (Bilder zählen als Tokens).

### 2.2 Datenmodell (`backend/models.py`)

- **`SharedList`** — geteilte Liste. **`id` ist eine UUID** und dient als
  Share-Link (jeder mit der UUID sieht die Liste; kein Login). Felder: `title`,
  `created_at`. `expenses` = 1:n mit `cascade="all, delete-orphan"`.
- **`Expense`** — eine Ausgabe. Felder: `title`, `amount` (float), `payer_name`,
  `split_ratio` (float, Default `0.5`), `category`, `created_at` (Zeitstempel,
  `server_default=now()` — dient Sortierung & Duplikats-Prüfung), `receipt_date`
  (nullable `Date`), **`currency`** (String(3), Default `'EUR'`) und
  **`exchange_rate`** (float, Default `1.0`).
  - **Multi-Currency (2026-07-21, Roadmap 2.0 #3):** `amount` ist der Betrag in
    der **Erfassungswährung** `currency`. `exchange_rate` ist der **EUR-Wert
    einer Einheit** dieser Währung; der EUR-Betrag ist damit stets
    `amount * exchange_rate` (für EUR ist der Kurs `1.0`). Kassensturz, Statistiken
    und die Gesamtsumme rechnen ausschließlich in EUR (Basiswährung).
  - **`split_ratio`-Konvention:** Anteil, den der **Zahler selbst** trägt.
    `0.5` = 50/50, `0.7` = Zahler trägt 70 %. Seit dem Advanced Split (Roadmap 3.0
    #3) nur noch **Fallback** (Altdaten + gescannte Bons ohne feine Aufteilung):
    Der Rest `amount * (1 - split_ratio)` wird bei **n>2** zu gleichen Teilen auf
    die **anderen** Personen verteilt (bei 2 Personen = die eine andere Person).
  - **`splits` (2026-07-21, Roadmap 3.0 #3):** explizite Pro-Person-Aufteilung als
    JSON-Objekt `{Name: Betrag}` — Beträge in der **Erfassungswährung** `currency`
    (analog zu `amount`; EUR-Wert = `Betrag * exchange_rate`). Die Summe ergibt
    exakt `amount` (das Frontend garantiert das über die 1-Cent-Verteilung).
    `NULL` = keine feine Aufteilung → der Kassensturz fällt auf `split_ratio`
    zurück. Ist die **maßgebliche Wahrheit** der Aufteilung, wenn gesetzt;
    `split_ratio` wird parallel kohärent gehalten (Eigenanteil des Zahlers).
  - **`receipt_date` (2026-07-20, To-Do 2/3):** von der KI gelesenes Bon-Datum,
    **nur beim Scan** gesetzt (bei manueller Eingabe `NULL`). Trägt die
    Duplikats-Prüfung: so wird derselbe Bon auch an einem **anderen Tag** erneut
    als Duplikat erkannt. Fehlt es, gilt ersatzweise `created_at`.
- **`CategoryRule` (2026-07-22, Epic 4.0 #3)** — gelernte Zuordnung
  „Empfänger-Stichwort → Kategorie" je Liste (Tabelle `category_rules`). Felder:
  `id`, `list_id` (FK, `cascade="all, delete-orphan"` über `SharedList.category_rules`),
  `recipient_keyword` (getrimmt/großgeschrieben), `category`. Fundament für den
  Kontoauszug-Import („Smart Memory"); die Anwendungslogik folgt später.

### 2.3 Wichtige Endpunkte (`backend/routers/lists.py`, Prefix `/api`)

| Methode & Pfad                                     | Zweck                                                        |
| -------------------------------------------------- | ----------------------------------------------------------- |
| `POST /api/lists`                                  | Neue geteilte Liste erstellen → `SharedListResponse`        |
| `GET  /api/lists/{list_id}`                        | Liste inkl. aller Ausgaben laden (404 wenn unbekannt)       |
| `GET  /api/lists/{list_id}/settlement`             | **Kassensturz N Personen** → `SettlementResponse` (Salden + minimale Zahlungen) |
| `POST /api/lists/{list_id}/expenses`               | Ausgabe manuell hinzufügen (`ExpenseCreate`)                |
| `PUT  /api/lists/{list_id}/expenses/{expense_id}`  | Ausgabe vollständig aktualisieren (`ExpenseUpdate`)         |
| `DELETE /api/lists/{list_id}/expenses/{expense_id}`| Ausgabe löschen → `204`                                     |
| `POST /api/lists/{list_id}/receipts`               | **Bon-Upload — asynchron** (multipart: `payer_name` + `receipt`-Bild) → **`202` `{"status":"processing","job_id":…}`** (Epic 4.0 #2, Job seit 2026-09-25) |
| `GET  /api/lists/{list_id}/receipt-jobs`           | Nicht quittierte Bon-Scans (neueste zuerst) → `list[ReceiptJobResponse]` — Frontend pollt |
| `DELETE /api/lists/{list_id}/receipt-jobs/{job_id}`| Job quittieren/verwerfen → `204` (idempotent)               |
| `POST /api/lists/{list_id}/bank-statement/parse`   | **Kontoauszug-PDF lesen** (multipart: `statement`) → `BankStatementPreview` (alle Buchungen + Kategorie + Duplikat-Flag; **speichert nichts**) |
| `POST /api/lists/{list_id}/bank-statement/import`  | Bestätigte Buchungen als **Einzelausgaben** anlegen (`BankImportRequest`) → `201 BankImportResponse` |

**Duplikats-Prüfung (Roadmap #2, präzisiert 2026-07-20):** Gilt nur noch für
`POST …/expenses` (manuell): prüft vor dem Speichern, ob bereits eine Ausgabe mit
**gleichem Betrag** (auf Cent gerundet) am **selben Datum** existiert. Als Datum
eines bestehenden Eintrags gilt sein `receipt_date` (falls gesetzt), sonst
`created_at`. Vergleichstag der neuen Ausgabe ist `heute`. Falls ja → **HTTP 409**
(`{"detail": …}`). Mit `?force=true` wird die Prüfung übergangen. Sie greift **nur
beim Neuanlegen**, nicht beim Bearbeiten (PUT). **Seit Epic 4.0 #2** läuft der
**Bon-Scan asynchron** (Fire & Forget) und macht **keine** interaktive
Duplikats-Prüfung mehr (passt nicht zu einer sofortigen 202-Antwort).

### 2.4 Ablauf Kassenbon-Scan (End-to-End)

> **Seit Epic 4.0 #2 asynchron (Fire & Forget):** Der Endpoint validiert nur,
> liest das Bild in den RAM und antwortet **sofort** mit `202`; die Schritte 2–7
> laufen in einem **FastAPI-`BackgroundTask`** (siehe 2.11). Der Nutzer wartet
> nicht mehr. **Seit 2026-09-25** legt der Upload einen `ReceiptJob` an; das
> Frontend pollt dessen Status und fügt die Ausgabe automatisch ein bzw. zeigt
> einen Fehler (siehe 2.12).

1. Frontend sendet Bild + `payer_name` als `multipart/form-data` an
   `POST /api/lists/{id}/receipts` (Content-Type setzt der Browser selbst).
2. Router prüft `content_type` (muss `image/*` sein → sonst 400), liest die Bytes
   und übergibt sie an den BackgroundTask. Ab hier läuft alles **nach** der
   202-Antwort: `analyze_receipt(image_bytes)`.
3. `ollama_client._prepare_image` verkleinert das Bild auf max.
   `MAX_IMAGE_PIXELS` (1,8 MP) und normalisiert auf JPEG (q90) — spart Tokens
   und Rechenzeit.
4. Bild → Base64 → an Ollama (`RECEIPT_PROMPT`, `format: json`, `num_ctx: 16384`,
   `temperature: 0`). Der Prompt fordert **zwingend** fünf Keys: `title`, `amount`,
   `date` (Kaufdatum, ISO `YYYY-MM-DD` oder `null`), `category`, `currency`
   (ISO-Code, Fallback `EUR`).
5. Antwort wird gegen `schemas.ReceiptAnalysis` validiert. `field_validator`
   repariert deutsche Betragsformate ("24,50 €" → `24.50`) und parst das Datum
   tolerant (ISO **und** deutsch `TT.MM.JJJJ`, angehängte Uhrzeit wird
   abgeschnitten). **Wichtig:** Das Datumsfeld heißt intern `receipt_date`, liest
   aber per **Alias** den JSON-Key `date` — der Bezeichner `date` als Feldname
   würde sonst den importierten `date`-Typ verschatten. Unlesbares/fehlendes
   Datum → `None` (der Scan schlägt deshalb **nicht** fehl).
6. Halluzinierte Kategorien werden auf `FALLBACK_CATEGORY` ("Unknown/Manuell")
   gemappt. Erlaubte Kategorien: **Lebensmittel, Kosmetik, Restaurant, Haushalt,
   Sonstiges**.
7. Für die gelesene `currency` wird der Tageskurs geholt (`currency.py`, EUR ohne
   API-Aufruf). Der BackgroundTask legt einen **fairen Split** über alle aktuell
   bekannten Personen der Liste + den Zahler an (`splits.fair_split`) und speichert
   die `Expense` (mit abgeleitetem `split_ratio`, `receipt_date`, `currency`,
   `exchange_rate`, `splits`) über eine **eigene** DB-Session. Fehler (OCR/Kurs/DB)
   werden geloggt **und** im `ReceiptJob` als `failed` + Ursache gespeichert
   (seit 2026-09-25); Erfolg setzt `done` + `expense_id`. Vor Schritt 3 prüft der
   Task, ob das Modell vorhanden ist, und lädt es sonst nach (Auto-Pull, 2.12).

### 2.5 Kassensturz-Logik (N Personen, seit To-Do 3 · 2026-07-20)

- Wohnt jetzt **im Backend** in `settlement.py` (`calculate_settlement`), erreichbar
  über `GET /api/lists/{id}/settlement`. Reine, DB-freie Logik (nur die
  Pydantic-Antwort-Schemas) → testbar und für spätere Clients wiederverwendbar.
  Das Frontend **holt** das Ergebnis und stellt es in `SettlementCard.tsx` dar
  (keine Algorithmus-Duplizierung Backend/Frontend).
- **Personen = eindeutige `payer_name`** aller Ausgaben **plus** alle in einer
  `splits`-Aufteilung genannten Namen (in Reihenfolge des ersten Auftretens).
  Dank Advanced Split (Roadmap 3.0 #3) taucht so auch ein reiner **Mit-Esser**,
  der nie selbst zahlt, im Kassensturz auf — sofern ihm eine Ausgabe einen Anteil
  zuweist. (Wer in gar keiner Ausgabe vorkommt, bleibt weiterhin unbekannt.)
- **Aufteilung:** Trägt eine Ausgabe eine explizite `splits`-Aufteilung, gilt
  **genau diese** (jede Person verbraucht ihren hinterlegten Betrag, in EUR
  umgerechnet). Ohne `splits` (Fallback): Zahler trägt `split_ratio·amount` selbst;
  der Rest `(1-split_ratio)·amount` wird gleichmäßig auf die **anderen** Personen
  verteilt. Für 2 Personen exakt äquivalent zur alten `balance.ts`-Logik.
- **Salden:** `net = gezahlt − verbraucht` je Person (Summe = 0). `net>0` bekommt
  Geld, `net<0` schuldet Geld. Beträge < 0,005 € gelten als ausgeglichen.
- **Debt Simplification:** Greedy — größter Schuldner zahlt an größten Gläubiger,
  bis alles 0 ist → höchstens `n-1` Überweisungen (praxistaugliche Standardlösung,
  nicht das NP-harte theoretische Minimum). Antwort: `SettlementResponse`
  = `{ balances: [{name, paid, share, net}], transactions: [{from_person, to_person, amount}] }`.
- **Frontend-Abruf:** `ListView` lädt das Settlement per Effekt neu, sobald sich
  `list` (die Ausgaben) ändert; das vorige Ergebnis bleibt währenddessen sichtbar.

### 2.6 Konfiguration (Environment-Variablen)

Wird ausschließlich über `docker-compose.yml` gesetzt; Code liest via `os.getenv`
mit sinnvollen Defaults.

| Variable                  | Default (Code)                  | Bedeutung                                  |
| ------------------------- | ------------------------------- | ------------------------------------------ |
| `DATABASE_URL`            | `postgresql://yousplit:...@db` | DB-Verbindung                              |
| `OLLAMA_URL`              | `http://ollama:11434`           | Ollama-Endpoint                            |
| `OLLAMA_MODEL`            | `qwen2.5vl:3b`                  | Vision-Modell für OCR                      |
| `OLLAMA_TIMEOUT_SECONDS`  | `480` (Compose) / `300` (Code)  | Timeout — CPU-Inferenz dauert 2–4 Min      |
| `OLLAMA_PULL_TIMEOUT_SECONDS` | `3600`                      | Timeout des automatischen Modell-Downloads (2026-09-25) |
| `LOG_LEVEL`               | `INFO`                          | Backend-Log-Level (`DEBUG` zeigt z. B. rohe KI-Antworten) |
| `OLLAMA_KEEP_ALIVE`       | `1m` (Compose, Epic 4.0 #1)     | Modell nur 1 Min im RAM halten (~4 GB) → Server-Schonung, dafür Kaltstart nach Pause |
| `FRANKFURTER_URL`         | `https://api.frankfurter.app/latest` | Wechselkurs-API (Roadmap 2.0 #3)      |
| `EXCHANGE_RATE_TIMEOUT_SECONDS` | `10`                      | Timeout des Kurs-Abrufs                    |

**Ollama CPU vs. GPU (Roadmap #4, 2026-07-20):** Der Default ist **CPU** und
startet auf jedem Host — `docker compose up` stürzt nie an fehlender GPU/NVIDIA-
Runtime ab. Die GPU ist ein **opt-in Override** (`docker-compose.gpu.yml`,
`deploy.resources.reservations.devices` → NVIDIA). Umschalten über `.env`
(`COMPOSE_FILE`, plattformunabhängiger `:`-Trenner via `COMPOSE_PATH_SEPARATOR`)
oder ad hoc: `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up`.
Voraussetzung für GPU: NVIDIA-GPU + NVIDIA Container Toolkit auf dem Host.

### 2.7 Frontend: Tab-Navigation & Statistiken (Roadmap 2.0 #2, 2026-07-21)

- **Tab-Struktur der Detailseite:** `ListView` bleibt schlanker Orchestrator und
  hält nur den aktiven Tab als State (`ListTab = "expenses" | "settlement" |
  "statistics"`). Die mobile-freundliche Tab-Leiste ist in `ListTabs.tsx`
  gekapselt (Segmented Control im `emerald`-Design, rein darstellend, meldet die
  Auswahl über `onChange`). Je Tab wird genau ein Block gerendert:
  - **„Ausgaben"** → `ExpenseForm` (Anlegen/Scannen) **und** `ExpenseList`
    (Formular und Liste gehören inhaltlich zusammen; der Empty-State-CTA der
    Liste fokussiert das Titelfeld des Formulars).
  - **„Kassensturz"** → `SettlementCard` (unverändert, s. 2.5).
  - **„Statistiken"** → `StatisticsBoard` (neu).
- **Charts (`recharts`):** Die Aggregation läuft **performant im Frontend** per
  `useMemo` über die ohnehin geladenen Ausgaben (kein neuer Endpunkt) und wird
  nur bei Änderung der Liste neu berechnet:
  - **Kategorie-Donut** (`PieChart`): Summe je `category`, absteigend sortiert,
    mit zentrierter Gesamtsumme und eigener Legende (Betrag + Prozentanteil).
    Kategorien werden **dynamisch aus den Daten** gebildet (nicht hartcodiert),
    leere Kategorie fällt auf „Sonstiges".
  - **Ausgaben je Person** (`BarChart`): Summe der `amount` je `payer_name`.
  - Farbschema: kühle **Emerald/Teal/Cyan**-Palette (nur der Donut nutzt die
    Palette semantisch; die Balken sind einheitlich Finanz-Grün = „Geld").
  - **Empty State**, wenn die Liste keine Ausgaben hat („Füge Ausgaben hinzu …").
- **Beträge/Prozente** werden über `format.ts` (`formatEuro`) bzw. `de-DE`-locale
  formatiert; Chart-Tooltips ebenfalls in Euro.

### 2.8 Multi-Currency / Fremdwährungen (Roadmap 2.0 #3, 2026-07-21)

Nutzer erfassen Ausgaben in EUR, **USD, CHF oder GBP**; gerechnet wird intern
immer in der Basiswährung **EUR**.

- **Kurs-Konvention (projektweit):** `exchange_rate` = **EUR-Wert einer Einheit**
  von `currency`. Der EUR-Betrag ist stets `amount * exchange_rate`; für EUR ist
  der Kurs `1.0`. Diese Konvention gilt identisch in `settlement.py`,
  `StatisticsBoard.tsx`, `ExpenseListItem.tsx` und der Header-Summe.
- **Kurs-Abruf (`backend/currency.py`):** gekapselter Zugriff auf die freie,
  Key-lose **Frankfurter-API** (`get_exchange_rate(currency)` →
  `GET {FRANKFURTER_URL}?from={WÄHRUNG}&to=EUR`, Feld `rates.EUR`). Kein anderer
  Code spricht direkt mit dem Dienst (wie bei `ollama_client.py`). Für EUR wird
  **kein** API-Aufruf gemacht (direkt `1.0`). **Wichtig:** `follow_redirects=True`,
  denn `api.frankfurter.app` antwortet mit **301** auf `api.frankfurter.dev`
  (Query-Parameter bleiben erhalten). Unterstützte Währungen (Roadmap 3.0 #2
  erweitert): `MAIN_CURRENCIES = (EUR, USD, CHF, GBP)` plus
  `MORE_CURRENCIES = (SEK, NOK, DKK, PLN, CZK, HUF, RON, BGN, ISK)` →
  `SUPPORTED_CURRENCIES = MAIN + MORE` (alle von Frankfurter unterstützt).
- **Wann wird abgerufen:** in `POST …/expenses` und `PUT …/expenses/{id}` (nur bei
  Währungswechsel) sowie im Bon-Scan `POST …/receipts`. Der Kurs wird **erst nach**
  der Duplikats-Prüfung geholt (spart Aufrufe). Der Client schickt **nie** den
  Kurs — nur die Währung; der Kurs wird serverseitig tagesaktuell ermittelt.
- **Fehlerverhalten:** Ist die Kurs-API nicht erreichbar/verwertbar, wirft
  `currency.py` `ExchangeRateError`, der Router übersetzt das in **HTTP 502** —
  **kein** stiller Fallback auf `1.0` (das würde die EUR-Salden verfälschen). EUR-
  Ausgaben sind davon nie betroffen.
- **Validierung:** `ExpenseCreate/Update.currency` wird auf Großschreibung
  normalisiert und muss in `SUPPORTED_CURRENCIES` liegen (sonst 422). Beim
  **Scan** ist die KI-Währung tolerant: Unbekanntes/Fehlendes fällt auf `EUR`
  zurück (der Scan schlägt daran nicht fehl). Der Prompt fragt `currency` als
  ISO-Code mit ab (Symbol €/$/£/CHF).
- **Frontend:** Währungs-Dropdown gekapselt in `CurrencySelect.tsx` (Roadmap 3.0
  #2, in `ExpenseForm` und `EditExpenseModal` identisch genutzt): zeigt zunächst
  nur die Hauptwährungen plus einen Punkt „Mehr…", der die europäischen
  Nebenwährungen aufklappt (ist bereits eine Nebenwährung gewählt, startet es
  aufgeklappt). Speist sich aus `MAIN_CURRENCIES`/`MORE_CURRENCIES`/`CURRENCIES`
  in `api.ts`. In der Ausgaben-Card zeigt `formatMoney(amount, currency)` den
  Originalbetrag (Fremdwährung mit ISO-Code, z. B. „50,00 USD"), darunter dezent
  `≈ formatEuro(amount * exchange_rate)`. EUR bleibt beim €-Symbol.

### 2.9 Advanced Split — Kostenaufteilung (Roadmap 3.0 #3, 2026-07-21)

Die Aufteilung einer Ausgabe ist ein eigener Block `AdvancedSplitter.tsx` in
`ExpenseForm` und `EditExpenseModal` (ersetzt das alte `SplitRatioInput`). Er
zeigt **immer alle bekannten Teilnehmer** der Liste — auch solche, die 0 zahlen.

- **Reine Rechenlogik in `splitMath.ts`** (bewusst ohne React/DOM → testbar):
  `distributeEvenly` (1-Cent-Verteilung), `redistributeUnlocked` (Locking),
  `resolveAmounts`/`resolveSplits` (exakte Summe), `fairEntries`, `convertMode`,
  `syncEntries`, `splitsFromRatio`. Die Komponente hält nur Zustand und ruft diese
  Helfer.
- **Drei Modi (Dropdown):** `%` (Prozent), `Betrag` (Erfassungswährung), `Anteile`
  (relative Gewichte). Prozent/Betrag mit **2 Nachkommastellen**; Autokorrektur
  (Clamp + Rundung) beim Verlassen des Feldes (`onBlur`).
- **Fairer Default:** eine neue Ausgabe startet im `%`-Modus mit gleichmäßiger
  Verteilung (z. B. 4 Personen → 25 % je).
- **Locking:** Ändert der Nutzer einen Wert, wird die Person „gelockt"; die
  übrigen (ungelockten) teilen sich den Rest **gleichmäßig** (zieht man bei X ab,
  bekommen die Ungelockten automatisch mehr, und umgekehrt). Ein Lock-Schalter je
  Zeile erlaubt Freigeben/Fixieren. Invariante: **ungelockt = automatisch
  balanciert**, **gelockt = manuell**.
- **1-Cent-Problem:** `resolveAmounts` normiert nicht-negative Gewichte auf den
  Gesamtbetrag; der Rundungsrest geht an die **erste ungelockte Person**, sodass
  die Summe der Anteile **immer exakt** `amount` ergibt (robust auch bei
  Über-Constraint — es entstehen nie negative Anteile).
- **Persistenz:** Beim Speichern liest das Formular per Ref `getResult()` →
  `{ splits, splitRatio }`. `splits` (`{Name: Betrag}`) geht ans Backend (siehe
  2.2), `split_ratio` = Eigenanteil des Zahlers bleibt als Fallback kohärent.
  Beim Bearbeiten einer Ausgabe **ohne** gespeicherte `splits` (Altdaten/Scan)
  wird die bisherige Aufteilung via `splitsFromRatio` **treu** vorbelegt.
- Gescannte Bons (`POST …/receipts`) bekommen **keine** feine Aufteilung
  (`splits=NULL`, `split_ratio=0.5`) — der Fallback greift.

### 2.10 Startseite / Dashboard (Roadmap 3.0 #1, 2026-07-21)

`Home.tsx` (Route `/`) ist ein Dashboard statt der alten reinen Anlege-Maske:

- **CTA „Neue Liste erstellen"** öffnet ein Titel-**Modal** → `createList` →
  Merkliste aktualisieren → Weiterleitung auf `/list/:id`.
- **Grid der zuletzt besuchten Listen** als anklickbare Cards (Titel + letzter
  Besuch), mit Empty State. Jede Card kann per „×" aus der Merkliste entfernt
  werden (löscht **nicht** die Liste selbst).
- **`recentLists.ts`** kapselt den `localStorage`-Zugriff (Key
  `yousplit:recent_lists`, `{id, title, lastVisit}[]`, max. 12, neueste zuerst;
  defensiv gegen kaputtes JSON). `ListView` ruft beim Laden `addRecentList`, sodass
  jede besuchte (auch per Share-Link geöffnete) Liste auf dem Gerät auftaucht.

### 2.11 Epic 4.0 — Asynchrone Verarbeitung & Kontoauszüge (Fundament, 2026-07-22)

Erster Baustein eines größeren Epics. In diesem Schritt gebaut:

- **Ressourcen-Schonung (#1):** `OLLAMA_KEEP_ALIVE=1m` in `docker-compose.yml` (das
  GPU-Override erbt das per Merge). Das Modell wird nach 1 Min Inaktivität aus dem
  RAM geworfen — wichtig für kleine Server. Kaltstart-Nachteil ist dank der neuen
  Fire-&-Forget-Verarbeitung verkraftbar.
- **„Fire & Forget"-Bon-Upload (#2):** `POST …/receipts` validiert nur Liste +
  Bildtyp, liest die Bytes und antwortet **sofort** mit `202 {"status":
  "processing"}`. OCR + Kursabruf + fairer Split + DB-Insert laufen in einem
  **FastAPI-`BackgroundTask`** (`_process_receipt_in_background` in `lists.py`).
  - **Eigene DB-Session:** Der Task nutzt `SessionLocal()` direkt — die
    Request-Session aus `get_db` ist nach der Antwort schon zu.
  - **Fairer Split:** `splits.fair_split(amount, persons)` verteilt den Betrag
    gleichmäßig (1-Cent-Rest an die erste Person, Konvention wie im Frontend) auf
    alle bekannten Personen der Liste (`settlement.collect_persons`) **plus** den
    Zahler; das Ergebnis landet als `splits`-JSON, `split_ratio` wird abgeleitet.
  - **Fehler** (OCR/Kurs/DB) werden nur ins Docker-Log geschrieben — dem Client
    kann nach der 202 nichts mehr gemeldet werden. **Bewusster Wegfall:** die
    interaktive 409-Duplikatswarnung entfällt beim Scan.
  - **Frontend:** kein blockierender Spinner mehr; nach der Auswahl sofort eine
    Erfolgsmeldung („Beleg wird im Hintergrund verarbeitet …") + Formular-Reset
    (`ExpenseForm`). `api.uploadReceipt` gibt `{status}` zurück (kein `force` mehr).
    Die neue Ausgabe erscheint erst beim nächsten Laden der Liste.
- **Fundament Kontoauszüge (#3):**
  - **`CategoryRule`** (Tabelle `category_rules`): `id`, `list_id` (FK, cascade-
    delete), `recipient_keyword` (getrimmt/großgeschrieben), `category`. „Smart
    Memory" für den späteren PDF-Import — merkt sich Empfänger→Kategorie. Schemas:
    `CategoryRuleCreate` / `CategoryRuleResponse`. **Noch keine Endpunkte/Logik** —
    reines Schema-Fundament.
  - **UI:** vierter Tab **„Kontoauszug"** (`ListTabs`, Icon `Landmark`) →
    `BankStatementView.tsx`: PDF-only Dropzone/Upload (Drag & Drop + Klick). Vorerst
    nur `console.log("PDF Upload triggered", file)` — der Parser folgt im nächsten
    Schritt.

> **Offene Punkte des Epics (nächste Schritte):** Status-Rückmeldung der
> Hintergrund-Verarbeitung ans Frontend (Polling/Websocket), PDF-Parser +
> `CategoryRule`-Matching, Endpunkte für die Regeln.

---

### 2.12 Bugfix: stille Scan-Fehler → Auto-Pull + Status-Rückmeldung + Logging (2026-09-25)

**Symptom:** Nach dem Fire-&-Forget-Umbau (2.11) passierte nach einem Bon-Upload
„nichts" — keine Ausgabe, keine Fehlermeldung. **Ursache laut Docker-Log:**
`Ollama Error (HTTP 404): model 'qwen2.5vl:3b' not found`. Das Modell fehlte,
weil `docker compose down -v` (für den `splitbill`→`yousplit`-Reset, siehe 4.6)
**auch das Volume `ollama_models` löscht**. Der Fehler landete nur im Log, weil
das Frontend nach der `202` nichts mehr erfuhr.

- **Modell-Auto-Pull (`ollama_client.py`):** `is_model_available()` (`GET
  /api/tags`, tolerant ggü. `:latest`) und `ensure_model()` (`POST /api/pull`,
  `stream:false`, `asyncio.Lock` gegen parallele Downloads, Double-Check).
  Aufgerufen (a) beim Backend-Start im Hintergrund (`ensure_model_on_startup`,
  12 Versuche à 5 s, weil Ollama evtl. noch hochfährt; blockiert den Start
  nicht), (b) vor jedem Scan im BackgroundTask (mit Hinweis im Job-`detail`) und
  (c) als Selbstheilung, falls `/api/chat` doch `404 … not found` liefert
  (laden + einmal wiederholen). Der manuelle `ollama pull` ist damit **nicht mehr
  nötig**; erster Start nach Volume-Verlust lädt ~3 GB.
- **Status-Rückmeldung (`ReceiptJob`, Tabelle `receipt_jobs`):** `id`, `list_id`
  (FK, cascade über `SharedList.receipt_jobs`), `payer_name`, `filename`,
  `status` (`processing`/`done`/`failed`), `detail` (Fortschritts-Hinweis),
  `error` (nutzerverständliche Ursache), `expense_id` (ohne FK), `created_at`,
  `updated_at`. Zustandswechsel gekapselt in `receipt_jobs.py` (je eigene kurze
  Session, „best effort"). `fail_orphaned_jobs()` im `lifespan` markiert nach
  einem Neustart/Reload hängengebliebene `processing`-Jobs als `failed` (der
  BackgroundTask stirbt mit dem Prozess). Neue Tabelle → `create_all` legt sie
  automatisch an (kein SQL/Reset nötig).
- **Frontend:** `useReceiptJobs(listId, onJobsCompleted)` fragt beim Öffnen der
  Liste und nach jedem Upload ab und pollt alle 4 s, **solange** ein Job
  `processing` ist. `done` → Liste neu laden (`getList`) + Job per DELETE
  quittieren. `failed` bleibt sichtbar, bis der Nutzer ihn verwirft.
  `ReceiptJobsPanel` (unter dem Formular im Ausgaben-Tab) zeigt Spinner +
  Hinweis bzw. rote Fehler-Card mit X. `ExpenseForm` zeigt nur noch kurz „Beleg
  wird hochgeladen …" und ruft danach `onReceiptQueued` (→ `refresh`).
  `ReceiptUploadResult` enthält jetzt `job_id`; neue API-Funktionen
  `getReceiptJobs`, `dismissReceiptJob`, Typ `ReceiptJob`.
- **Logging (`logging_setup.py`):** Alle `print(...)` ersetzt durch Modul-Logger
  (`yousplit.receipts`, `yousplit.ollama`, `yousplit.currency`, `yousplit.main`),
  Format `Zeit LEVEL [logger] Nachricht`, Level via `LOG_LEVEL`. Jeder Scan loggt
  unter seiner Job-ID: angenommen → Start → erkannte Werte → fertig (Dauer,
  Ausgabe-ID) bzw. Fehler; Ollama loggt Analysedauer, Timeouts, Modell-Download.
  Erfolgreiche Polling-Requests (`GET …/receipt-jobs` 200) werden im
  uvicorn-Access-Log ausgefiltert. Nützliche Filter:
  `docker compose logs backend | findstr "yousplit.receipts"` bzw.
  `… | findstr "ERROR WARNING"`.
- **Verifikation (Container, 2026-09-25):** Backend mit SQLite + nachgebautem
  Ollama (404 → Pull → Analyse bzw. HTTP 500) und echter Vite-UI per Playwright:
  Spinner → Ausgabe erscheint automatisch; Fehler-Card mit Ursache; Modell-
  Download-Hinweis; verwaiste Jobs nach Neustart → `failed`. Typecheck, Lint,
  Build grün. **Nicht** gegen echtes Postgres/Ollama getestet.

---

### 2.13 Kontoauszug-Import: PDF → Lebensmittel-Ausgaben (Epic 4.0 #3, 2026-10-02)

**Ziel:** Nutzer lädt einen Kontoauszug (PDF) hoch; alle **Lebensmitteleinkäufe**
werden erkannt und als Ausgaben in die Liste übernommen.

**Entscheidungen (mit dem Nutzer geklärt):** (1) **generischer Parser** für
mehrere deutsche Banken statt eines bankspezifischen Layouts; (2) **Python-Parser
+ Händlerliste** (kein LLM) — deterministisch, schnell, lokal; (3) **jede Buchung
wird einzeln als Ausgabe angelegt**. Zusätzlich (Sicherheitsnetz wegen des
generischen Parsers): immer eine **Vorschau** vor dem Import.

- **`backend/bank_statement.py`** (rein, ohne DB/FastAPI, nur `pdfplumber`):
  - `extract_lines(pdf_bytes)` → Textzeilen; `StatementParseError` bei defektem/
    verschlüsseltem/eingescanntem PDF (kein Text → **kein OCR**).
  - `parse_lines(lines)` → `ParseResult(bookings, warnings)`. Eine Buchung beginnt
    mit einer Zeile, die mit `TT.MM.[JJ[JJ]]` startet (ein direkt folgendes
    zweites Datum = Valuta wird verworfen); datierte Folgezeilen **ohne Betrag**
    (ING-Valuta-Zeile) und undatierte Zeilen ergänzen den Verwendungszweck.
    Betrag = deutscher Dezimalbetrag (`1.234,56`), Vorzeichen vorn/hinten
    (`-12,34`/`12,34-`) oder `S`/`H`. Saldo-/Übertragszeilen, Seitenköpfe/-füße
    werden ausgeblendet. Bei Betrags- **und** Saldospalte gilt der vorletzte Betrag.
    Jahr fehlt in der Buchungszeile → häufigstes Jahr aus dem Dokument; Dez→Jan-
    Auszüge ohne Jahr werden korrigiert.
  - **Vorzeichen-Konvention:** Gibt es im Dokument explizite Ausgaben (`-`/`S`),
    aber keine expliziten Einnahmen (`+`/`H`), sind Beträge **ohne** Vorzeichen
    Gutschriften (Sparkasse-Stil). Sonst Annahme „Ausgabe", außer Wörter wie
    GUTSCHRIFT/GEHALT/ERSTATTUNG → `sign_guessed=True` + Warnung in der Vorschau.
  - `classify(description, rules)`: (a) gelernte **`CategoryRule`**-Stichwörter der
    Liste (**Vorrang**, längstes Stichwort gewinnt), (b) die Händlerliste
    **`backend/food_merchants.txt`** (Supermärkte/Discounter/Bio/Bäcker/Metzger/
    Drogerien/Lebensmittel-Lieferdienste für DE, AT, CH, Europa, USA/Kanada,
    LatAm, Asien-Pazifik, Afrika). **Dort von Hand erweitern** — Format steht im
    Dateikopf: ein Eintrag je Zeile, `#` = Kommentar, `*NAME` = auch als Teil eines
    Worts (für deutsche Zusammensetzungen wie `*FLEISCHEREI` → „Landfleischerei"),
    sonst nur ganzes Wort (`SPAR` trifft nicht `SPARKASSE`). Die Datei wird per
    mtime-Cache bei Änderung neu gelesen (**kein Neustart/Neubau nötig**).
    Normalisierung (`_fold`): Großschreibung, Umlaute (Ä→AE), Akzente weg,
    Sonderzeichen → Leerzeichen („E-Center" = „E CENTER", „PayPal *LIDL" matcht).
    **Drogerien (dm, Rossmann, Budnikowsky) zählen auf Wunsch als Lebensmittel**;
    Lieferando & Co. (Restaurant-Lieferdienste) bewusst nicht. Der Anzeigename
    („Landfleischerei", „Scholand") kommt aus dem Buchungstext.
- **Endpunkte** (`routers/lists.py`, Tabelle 2.3): `…/bank-statement/parse` ist
  bewusst `def` (CPU-gebunden → Threadpool), prüft `%PDF`-Magic + max. 15 MB, gibt
  **alle** Buchungen (`BankTransaction`: `amount` negativ = Ausgabe, `category`,
  `label`, `is_food`, `duplicate`, `sign_guessed`) + `warnings` zurück und
  speichert **nichts** (PDF wird nicht aufbewahrt). `duplicate` = gleicher Betrag
  am selben Tag existiert schon (wie Duplikatsprüfung, gegen `receipt_date` bzw.
  `created_at`). `…/import` legt je Item eine `Expense` an (EUR, Kurs 1.0,
  `receipt_date` = Buchungsdatum, Kategorie Default „Lebensmittel", Titel = Händler)
  mit `fair_split` auf alle Listen-Personen + Zahler; ein Commit (alles oder nichts).
- **Frontend (`BankStatementView.tsx`):** Dropzone → Spinner → Vorschau: erkannte
  Lebensmittel (vorausgewählt, Duplikate **nicht**), einklappbare „Weitere
  Ausgaben" zum Nachtragen übersehener Treffer, Zahler-Dropdown (Platzhalter
  „Bitte wählen …", gemerkter Name aus `payerStorage.ts`), Button mit Anzahl +
  Summe → Erfolgsansicht; `ListView` lädt danach die Liste neu. Einnahmen werden
  nur gezählt („werden ignoriert"). API: `parseBankStatement`, `importBankStatement`.
- **Neue Abhängigkeit:** `pdfplumber` (`backend/requirements.txt`) →
  **`docker compose up --build`** nötig (Backend-Image neu bauen).
  `pdfplumber` wird in `extract_lines` **lazy** importiert: fehlt es (Image nicht
  neu gebaut), startet das Backend trotzdem und nur der Kontoauszug-Import meldet
  einen Hinweis. (Vorfall 2026-10-02: ein Top-Level-Import ließ das Backend ohne
  neu gebautes Image gar nicht mehr starten → keine Listen erreichbar. Nach
  Backend-Änderungen ggf. `docker compose restart backend`, siehe Docker-Hinweis
  Windows-Bind-Mount in 4.6.)
- **Verifikation (Container, 2026-10-02):** 14 `unittest`-Tests (Parser-Layouts
  Sparkasse/ING-Stil, Vorzeichen, Saldospalte, Jahreswechsel, Klassifikation);
  synthetische Test-PDFs (1- und mehrseitig, reportlab) durch `pdfplumber`;
  Backend-Endpunkte per `TestClient` + SQLite; UI per Playwright (Upload →
  Vorschau → Nachtragen → Import → Liste/Kassensturz). Typecheck + Lint grün.
  **Nicht getestet** mit einem **echten** Kontoauszug und nicht gegen Postgres.
- **Bekannte Grenzen:** kein OCR für eingescannte PDFs; Layouts mit Soll-/Haben-
  **Spalten** ohne Vorzeichen werden nur über die Konvention/Schlagwörter erraten;
  Betragsangaben in Fremdwährung werden als EUR gelesen; `CategoryRule`-Matching
  ist verdrahtet, aber es gibt **noch keine Endpunkte/UI zum Anlegen der Regeln**
  (und kein „Als Lebensmittel merken" in der Vorschau).

---

## 3. Coding-Standards

### 3.1 Grundprinzipien (Clean Code)

- **Lesbarkeit vor Cleverness.** Sprechende Namen, kleine Funktionen mit einer
  klaren Aufgabe, frühe Rückgabe (Guard Clauses) statt tiefer Verschachtelung.
- **Trennung der Zuständigkeiten** respektieren: DB-Zugriff in Modellen/Router,
  KI-Kommunikation nur in `ollama_client.py`, HTTP-Aufrufe des Frontends nur in
  `api.ts`. Keine Schichtvermischung.
- **Keine Duplizierung von Wahrheit:** TS-Typen in `api.ts` spiegeln die
  Pydantic-Schemas. Ändert sich ein Schema, beide Seiten anpassen.
- **Fehler laut, aber kontrolliert:** Domänenfehler als eigene Exceptions
  (`ReceiptAnalysisError`), im Endpoint in passende HTTP-Codes übersetzen
  (z. B. Ollama-Ausfall → `502`, unbekannte Liste → `404`).

### 3.2 Deutsche Kommentare (verbindlich)

- **Kommentare und Docstrings auf Deutsch.** Sie erklären das **Warum**, nicht
  das offensichtliche **Was**. Vorbild sind die bestehenden Dateien (z. B. der
  Kommentar zu `split_ratio` oder `OLLAMA_KEEP_ALIVE`).
- **Bezeichner (Variablen/Funktionen/Klassen) bleiben englisch** (`calculate_settlement`,
  `payer_name`) — nur Kommentare/Doku sind deutsch. Fachbegriffe der Domäne
  ("Kassensturz", "Ausgabe") dürfen deutsch sein, wo sie nutzernah sind.
- Umlaute (ä/ö/ü/ß) sind in `.py`/`.ts`/`.md` erlaubt (UTF-8). In `.yml`/`.env`
  wird zur Sicherheit oft `ae/oe/ue/ss` geschrieben — innerhalb einer Datei
  konsistent bleiben.
- Auskommentierten "toten" Code nicht liegen lassen — löschen (Git ist das Archiv).

### 3.3 Backend-Konventionen (Python/FastAPI)

- **Typannotationen überall** (Parameter + Rückgabe). SQLAlchemy im 2.0-Stil
  (`Mapped[...]`, `mapped_column`). Pydantic v2 (`ConfigDict(from_attributes=True)`).
- **DB-Session** nur über `Depends(get_db)`. Nach Schreiboperationen
  `commit()` + `refresh()`.
- **Logging:** Fehler mit `print(..., flush=True)` ins Docker-Log schreiben
  (Muster wie in `ollama_client.py`), damit sie im Container sichtbar sind — nie
  Details still ans Frontend geben.
- **Router** dünn halten: Validierung + Orchestrierung; fachliche Logik in eigene
  Module (wie `ollama_client.py`) auslagern.

### 3.4 Frontend-Konventionen (React/TS)

- **TypeScript strict**, keine `any`-Flucht. Props/Datentypen explizit typisieren.
- **Alle Netzwerkaufrufe** über Funktionen in `api.ts` (nie `fetch` in
  Komponenten). Fehler laufen zentral über `handleResponse` (liest FastAPIs
  `{"detail": ...}`).
- **Tailwind** für Styling (Utility-First, kein separates CSS pro Komponente),
  **`lucide-react`** für Icons.
- Komponenten fokussiert und wiederverwendbar; reine Berechnungslogik (wie das
  Settlement im Backend `calculate_settlement`) von der Darstellung trennbar halten.

### 3.5 Modulstruktur — Faustregeln

- **Neuer Endpunkt:** Schema in `schemas.py` → Logik ggf. in eigenes Modul →
  Route in `routers/…` → TS-Typ + Funktion in `api.ts` → UI.
- **Neue fachliche Domäne** (z. B. zukünftige Settlement-Berechnung): eigenes
  Backend-Modul statt Anbau an `lists.py`.
- Ein Modul = eine Verantwortung. Wächst `lists.py` zu stark, nach Ressourcen
  aufteilen.

### 3.6 Refactoring-Richtlinien (Stand heute, 2026-07-20)

Leitplanken aus dem Clean-Code-Durchgang (Roadmap #5) — bei künftigen Änderungen
fortführen:

- **Komponenten-Größe (Frontend):** Seiten bleiben schlanke **Orchestratoren**.
  Wird eine Datei groß (Richtwert > ~250 Zeilen) oder vermischt sie mehrere
  Belange, kohärente Blöcke als eigene Komponente auslagern. Vorbild: `ListView`
  koordiniert nur (Laden, Edit/Delete) und delegiert an `ListHeader`,
  `SettlementCard`, `ExpenseForm`, `ExpenseList`.
- **Feature vs. Darstellung:** Rein darstellende Teile (`ListHeader`,
  `ExpenseListItem`) bekommen nur Props + Callbacks und keinen eigenen Fach-State.
  Ein zusammenhängendes Feature mit eigenem Zustand (`ExpenseForm`: Eingabe,
  Zahler-Erkennung, Scan, Duplikat) kapselt seinen State selbst und meldet nach
  außen nur das Ergebnis (`onExpenseAdded`).
- **State auf einen geänderten Prop/Param spiegeln:** per **render-phase**
  `if (prev !== next) setState(...)`, nicht per Effekt (vermeidet die
  `react-hooks/set-state-in-effect`-Regel). Datenladen bleibt im Effekt, setzt
  State aber nur in den Promise-Callbacks.
- **Backend-Router dünn halten:** Endpoints validieren + orchestrieren; fachliche
  bzw. wiederholte Logik in Helfer/Module auslagern (z. B. `_ensure_image`,
  `_analyze_or_502`, `_utc_today`, `settlement.calculate_settlement`). KI-Zugriff
  ausschließlich in `ollama_client.py`.
- **Kommentare:** deutsch, erklären das **Warum/Wie** komplexer Stellen
  (Settlement-Greedy, Duplikats-Datum, Ollama-Alias `date`→`receipt_date`,
  localStorage-Geräteerkennung). Triviales weglassen.
- **Eine Wahrheit:** TS-Typen in `api.ts` spiegeln die Pydantic-Schemas — bei
  Schema-Änderungen beide Seiten nachziehen.

---

## 4. Aktueller Status & Nächste Schritte

### 4.1 Aktueller Stand (MVP läuft ✅)

- Listen erstellen und per **UUID-Link teilen** (kein Login).
- Ausgaben manuell hinzufügen, **bearbeiten** (PUT) und **löschen** (DELETE).
- **Kassenbon-Scan** funktioniert (Ollama `qwen2.5vl:3b`, Bildverkleinerung,
  robustes JSON-Parsing inkl. deutscher Beträge **+ Bon-Datum**, Kategorie-Fallback).
- **Duplikats-Prüfung** (gleicher Betrag + Datum) mit „Trotzdem speichern" — beim
  Scan über das KI-extrahierte Bon-Datum, ohne KI-Neu-Analyse.
- **Sortierbare, scrollbare** Ausgabenliste (Datum/Betrag, Default neueste zuerst).
- **Kassensturz für N Personen** funktional (Backend `settlement.py` +
  `SettlementCard.tsx`), inkl. Debt Simplification (minimale Überweisungen).
- **Zahler-Dropdown** mit „Neue Person hinzufügen …" und **Geräte-Erkennung**
  (zuletzt genutzter Name pro Liste im `localStorage`, im Dropdown vorausgewählt).
- **Ausgabendatum:** eigener `DatePicker` (Kalender-Grid, Monats-Pfeile,
  Jahr-Dropdown 2020…heute+1, Default heute) im Formular; jede Ausgabe zeigt ihr
  Datum (`receipt_date`, sonst `created_at`) dezent in der Card.
- **UI/UX-Redesign (Roadmap #1) umgesetzt** (2026-07-20): Mobile-First, Finanz-Grün
  (`emerald`), einheitliches Card-Design (`rounded-xl border border-gray-100 bg-white
  shadow-sm`), `lucide-react`-Ikonografie, freundlicher Empty State mit CTA. Dabei
  **Build-Bug behoben:** `@tailwindcss/vite` war in `vite.config.ts` nicht registriert
  → Tailwind-Utilities wurden nicht generiert (komplett ungestyltes UI). Jetzt gefixt.

### 4.2 Roadmap (geplante Arbeitspakete)

> **Reihenfolge & Priorität mit dem Team abstimmen.** Pro Punkt: erst Ansatz
> klären, dann umsetzen, dann diese Datei aktualisieren.

1. **UI/UX modernisieren & übersichtlicher machen.** ✅ **Erledigt (2026-07-20).**
   Umgesetzt in `App.tsx`, `pages/Home.tsx`, `pages/ListView.tsx`,
   `components/BalanceCard.tsx`: Mobile-First, Finanz-Grün (`emerald`), Card-Design
   `rounded-xl border border-gray-100 bg-white shadow-sm`, großzügiges Spacing,
   `lucide-react`-Icons (`Camera`, `Receipt`, `Users`, …), Empty State mit CTA.
   Logik (Routing, API-Calls, State) unverändert.
   **Nachgezogen (2026-07-20):** Bearbeiten/Löschen pro Eintrag (`Pencil`/`Trash2`,
   Modal + Bestätigungsdialog), scrollbare Ausgabenliste (`max-h-[60vh]`,
   fixierter Header), Sortierung (Datum/Betrag, Default „Neueste zuerst").

2. **Duplikats-Prüfung beim Speichern.** ✅ **Erledigt (2026-07-20).**
   `Expense` um `created_at` erweitert; Backend erkennt **gleicher Betrag + selber
   Tag** und antwortet mit **HTTP 409** (Details siehe 2.3). Frontend zeigt eine
   Warnung „Trotzdem speichern?" und kann per `force=true` erzwingen — für den
   manuellen wie den Scan-Pfad. Prüfung greift nicht beim Bearbeiten.

3. **Kassensturz für > 2 Personen.** ✅ **Erledigt (2026-07-20).**
   Als testbarer Backend-Endpunkt `GET /api/lists/{id}/settlement` umgesetzt
   (`settlement.py`, Greedy-Debt-Simplification, ≤ n-1 Überweisungen). Das
   Frontend holt das Ergebnis und zeigt es in `SettlementCard.tsx` im
   `emerald`-Card-Design ("wer schuldet wem wie viel" + Salden je Person). Details
   siehe **2.5**. Die alte 2-Personen-Logik (`balance.ts`/`BalanceCard.tsx`) wurde
   ersetzt und entfernt.
   **Mitgeliefert (2026-07-20):** Zahler-**Dropdown** mit Geräte-Erkennung
   (`localStorage` pro Liste) und die Nachbesserungen zum Bon-Scan (Bon-Datum in
   der Duplikats-Prüfung; „Alles ausgeglichen" ohne Text-Emoji, da SVG-Icon davor).

4. **`docker-compose.yml`: dynamische GPU-Nutzung für Ollama.** ✅ **Erledigt (2026-07-20).**
   Umgesetzt als **Override-Strategie mit CPU-sicherem Default**: Basis-Compose
   lässt Ollama auf der CPU (startet überall, kein Absturz an fehlender GPU).
   Neues `docker-compose.gpu.yml` ergänzt die NVIDIA-Reservierung
   (`deploy.resources.reservations.devices`, `count: all`, `capabilities: [gpu]`).
   Umschalten portabel über `.env` (`COMPOSE_FILE` + `COMPOSE_PATH_SEPARATOR=:`)
   oder ad hoc via `-f docker-compose.yml -f docker-compose.gpu.yml`. Details in
   **2.6**. Beide Merges per `docker compose config` verifiziert.

5. **Code-Refactoring & deutsche Kommentierung nach Clean-Code-Standards.**
   ✅ **Erledigt (2026-07-20).** `ListView.tsx` (855 Zeilen) in einen schlanken
   Orchestrator plus fokussierte Komponenten zerlegt (`ListHeader`, `ExpenseForm`,
   `ExpenseList`, `ExpenseListItem`). Backend-Router entschlackt (`_ensure_image`,
   `_analyze_or_502`, `_utc_today`) und alle Endpoints/Modelle/Schemas mit
   deutschen Docstrings versehen. Regeln festgehalten in **3.6**. Typecheck, Lint
   und Build grün; Kernflüsse (Hinzufügen, Scan-Duplikat, N-Personen-Kassensturz,
   Edit inkl. Datum, Löschen) im Browser gegengetestet.

### 4.3 Roadmap 2.0 (Sprint 2.0)

> Neuer Sprint nach abgeschlossenem MVP. Gleiches Vorgehen wie oben: pro Punkt
> erst Ansatz klären, dann umsetzen, dann diese Datei fortschreiben.

1. **OCR-Härtetest.** ✅ **Erledigt (2026-07-21).** End-to-End-Test des Scan-Pfads
   mit einem echten Lidl-Bon (`test_bon.png`) gegen den laufenden Stack
   (temporärer Container im `yousplit_default`-Netz → `POST /api/lists/{id}/receipts`).
   **Befund:** `title` (Lidl), `amount` (137.77) und `category` (Lebensmittel)
   wurden zuverlässig gelesen; das **`receipt_date` kam als `null`**, obwohl es
   (deutsch `05.12.2025`) klar auf dem Bon stand. **Fix in `ollama_client.py`:**
   `RECEIPT_PROMPT` gehärtet (Datum ist fast immer vorhanden, typische Fundstellen,
   explizite Umwandlung `TT.MM.JJJJ` → `YYYY-MM-DD`) und `options.temperature = 0`
   für deterministische, faktentreue Extraktion. Danach in zwei Läufen
   reproduzierbar alle vier Felder korrekt (`receipt_date = 2025-12-05`). Das
   Wegwerf-Testskript wurde nach dem Test wieder entfernt.
2. **Statistiken & Charts.** ✅ **Erledigt (2026-07-21).** Visuelle Auswertung der
   Ausgaben mit **`recharts`**: Kategorie-**Donut** (prozentuale Verteilung, eigene
   Legende, zentrierte Gesamtsumme) und **Balkendiagramm** „Wer hat wie viel
   bezahlt?" je Person. Neue Komponente `StatisticsBoard.tsx` im `emerald`-Design
   inkl. Empty State; Aggregation performant im Frontend via `useMemo`. Zugänglich
   über eine neue **Tab-Navigation** (`ListTabs.tsx`: Ausgaben / Kassensturz /
   Statistiken), die `ListView` schlank hält. Details siehe **2.7**. Typecheck,
   Lint und ein Browser-Durchgang (alle Tabs, korrekte Summen/Prozente) grün.
3. **Fremdwährungen.** ✅ **Erledigt (2026-07-21).** Multi-Currency (EUR, USD, CHF,
   GBP): `Expense` um `currency` + `exchange_rate` erweitert; Kurs-Abruf über die
   Key-lose **Frankfurter-API** in `backend/currency.py` (serverseitig, tagesaktuell,
   `follow_redirects` wegen `.app`→`.dev`). Kassensturz, Statistiken und Header-Summe
   rechnen in **EUR** (`amount * exchange_rate`); die Ausgaben-Card zeigt Original +
   `≈ EUR`. Währungs-Dropdown in `ExpenseForm`/`EditExpenseModal`, OCR-Prompt liest
   `currency` mit (Fallback EUR). Details siehe **2.8**. Kurs-Fehler → HTTP 502
   (kein stiller 1.0-Fallback). Backend-E2E (USD/CHF mit realen Kursen) + Frontend
   (Typecheck, Lint, Browser) verifiziert.
   **Mitgeliefert (2026-07-21):** (a) **Cleanup** `splitbill` → `yousplit` in Compose,
   `database.py`, `main.py`, Doku (DB-Reset via `docker compose down -v` durch den
   Nutzer nötig — neue Zugangsdaten). (b) **Split-Regler-UI** überarbeitet: neue
   Komponente `SplitRatioInput.tsx` (Slider **+** direkt editierbares %-Feld, ganze
   Prozente, bidirektional) ersetzt die alte Text-Anzeige in `ExpenseForm` und
   `EditExpenseModal`. _(In Roadmap 3.0 #3 wiederum durch `AdvancedSplitter`
   ersetzt und entfernt.)_

### 4.4 Roadmap 3.0 (Sprint 3.0)

> Gleiches Vorgehen: pro Punkt erst Ansatz klären, dann umsetzen, dann diese Datei
> fortschreiben.

1. **Landingpage & Listen-Verwaltung.** ✅ **Erledigt (2026-07-21).** `Home.tsx`
   (Route `/`) ist jetzt ein Dashboard: markanter CTA „Neue Liste erstellen"
   (Titel-Modal → `createList` → Weiterleitung) und ein Grid der zuletzt besuchten
   Listen als anklickbare Cards. Merkliste im `localStorage`
   (`yousplit:recent_lists`) gekapselt in `recentLists.ts`; `ListView` protokolliert
   jeden Besuch. Details siehe **2.10**.
2. **Währungen erweitern.** ✅ **Erledigt (2026-07-21).** `SUPPORTED_CURRENCIES` um
   9 europäische Nebenwährungen (SEK, NOK, DKK, PLN, CZK, HUF, RON, BGN, ISK)
   erweitert (Backend `currency.py` + Frontend `api.ts` gespiegelt, alle
   Frankfurter-kompatibel). Neues `CurrencySelect.tsx` zeigt die Hauptwährungen und
   klappt via „Mehr…" die Nebenwährungen auf. Details siehe **2.8**.
3. **Advanced Split-Logik.** ✅ **Erledigt (2026-07-21).** Neuer Block
   `AdvancedSplitter.tsx` (in `ExpenseForm` + `EditExpenseModal`) über **alle**
   Teilnehmer, mit 3 Modi (%/Betrag/Anteile), Locking-Mechanismus und exakter
   1-Cent-Verteilung. Rechenlogik rein & testbar in `splitMath.ts`. **Full-Stack:**
   neue `splits`-JSON-Spalte (`{Name: Betrag}`) im `Expense`-Modell + Schemas;
   `settlement.py` nutzt explizite Anteile (Fallback `split_ratio`) und bezieht
   auch reine Mit-Esser ein. Details siehe **2.9** (+ 2.2, 2.5). Typecheck, Lint und
   Build grün. **Offen für den Nutzer:** DB-Migration der `splits`-Spalte (siehe
   4.6) und ein End-to-End-Browser-Test gegen den laufenden Stack.

### 4.5 Epic 4.0 — Asynchrone Verarbeitung & Kontoauszüge

> Großes Epic; hier wurde das **Fundament** gelegt (2026-07-22). Vorgehen wie
> bisher: pro Schritt erst Ansatz klären, dann umsetzen, dann diese Datei
> fortschreiben.

1. **Ressourcen-Schonung (Ollama).** ✅ **Erledigt (2026-07-22).**
   `OLLAMA_KEEP_ALIVE=1m` in `docker-compose.yml` (GPU-Override erbt es per Merge).
   Details siehe **2.11** und Config-Tabelle **2.6**.
2. **„Fire & Forget" (asynchroner Bon-Upload).** ✅ **Erledigt (2026-07-22).**
   `POST …/receipts` antwortet sofort `202 {"status":"processing"}`; OCR + fairer
   Split + DB-Insert laufen im `BackgroundTask` (eigene Session, `splits.fair_split`).
   Frontend: kein Blockier-Spinner, sofortige Erfolgsmeldung + Reset. Details siehe
   **2.11** (+ 2.3, 2.4). Interaktive Duplikatswarnung entfällt beim Scan.
3. **Fundament Kontoauszüge (PDF & Smart Memory).** ✅ **Erledigt (2026-07-22).**
   Neues Modell `CategoryRule` (+ Schemas) als „Smart Memory"; vierter Tab
   „Kontoauszug" (`ListTabs`) mit `BankStatementView.tsx` (PDF-only Dropzone,
   vorerst nur `console.log`). Details siehe **2.11**. **Noch offen (nächste
   Schritte):** PDF-Parser, `CategoryRule`-Matching, Regel-Endpunkte.
   ~~Status-Rückmeldung der Hintergrund-Verarbeitung~~ ✅ erledigt 2026-09-25
   (Receipt-Jobs + Polling, siehe **2.12**).
   **Hinweis DB:** Die neue Tabelle `category_rules` legt `Base.metadata.create_all`
   beim nächsten Backend-Start **automatisch** an (create_all erzeugt fehlende
   Tabellen) — ein voller `down -v`-Reset ist dafür **nicht zwingend**, ein
   `docker compose up`/`restart backend` genügt.

4. **Kontoauszug → Lebensmittel-Import (PDF-Parser).** ✅ **Erledigt (2026-10-02), mit generischem Parser — noch am echten Auszug zu prüfen.**
   Upload → Parser (`bank_statement.py`) → Vorschau → Einzelausgaben-Import.
   Details siehe **2.13**. **Noch offen:** (a) mit einem **echten** Kontoauszug
   der Nutzer-Bank gegentesten und den Parser ggf. nachschärfen; (b) Endpunkte +
   UI für `CategoryRule` („Als Lebensmittel merken", Regeln verwalten);
   (c) Händlerliste pflegen (`food_merchants.txt`).
5. **Komplettanalyse & Training der Kontoauszüge (Zukunft, Konzept offen).**
   📌 **Vorgemerkt (2026-10-02).** Langfristiges Ziel: Kontoauszüge werden **nicht
   nur auf Lebensmittel** gefiltert, sondern **vollständig analysiert** — alle
   Buchungen (Einnahmen + Ausgaben) werden kategorisiert (Miete, Abos,
   Versicherung, Freizeit, Gehalt, …), und das System soll aus Nutzerkorrekturen
   **lernen/trainiert werden** (Ausbau von `CategoryRule` zum „Smart Memory"
   bzw. ggf. KI-gestützte Klassifikation über lokales Ollama). **Wie genau das
   Training aussehen soll, ist noch zu klären** (z. B. reine Regel-Lernkurve vs.
   LLM-Klassifikation vs. Hybrid; Datenhaltung; Feedback-UI; Datenschutz — alles
   lokal). Beim Entwurf von Punkt 4 deshalb **erweiterbar** bauen: Parser liefert
   *alle* Buchungen als strukturierte Liste, der Lebensmittel-Filter ist nur
   die erste Kategorie-Stufe.

### 4.6 Bekannte Einschränkungen / Tech-Debt

- **Keine Migrationen (Alembic fehlt):** Schema entsteht via `create_all`, das
  bestehende Tabellen **nicht** ändert. Feld-Ergänzungen müssen auf laufenden DBs
  von Hand nachgezogen werden. Beispiel `created_at` (2026-07-20) wurde per
  `ALTER TABLE expenses ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL
  DEFAULT now();` eingespielt. **Neu (2026-07-20, To-Do 3):** die Spalte
  `receipt_date` (nullable) — auf laufender DB einmalig per
  `ALTER TABLE expenses ADD COLUMN IF NOT EXISTS receipt_date DATE;` nachziehen.
  **Neu (2026-07-21, Roadmap 2.0 #3):** die Spalten `currency` + `exchange_rate` —
  auf laufender DB einmalig per `ALTER TABLE expenses ADD COLUMN IF NOT EXISTS
  currency VARCHAR(3) NOT NULL DEFAULT 'EUR'; ALTER TABLE expenses ADD COLUMN IF
  NOT EXISTS exchange_rate DOUBLE PRECISION NOT NULL DEFAULT 1.0;` nachziehen.
  **Neu (2026-07-21, Roadmap 3.0 #3):** die nullable Spalte `splits` (Pro-Person-
  Aufteilung als JSON) — auf laufender DB einmalig per
  `ALTER TABLE expenses ADD COLUMN IF NOT EXISTS splits JSON;` nachziehen (Postgres
  akzeptiert auch `JSONB`). **Neu (2026-07-22, Epic 4.0 #3):** die **neue Tabelle**
  `category_rules` — anders als Spalten-Ergänzungen legt `create_all` **neue
  Tabellen automatisch** beim nächsten Backend-Start an, hier ist also **kein**
  manuelles SQL und **kein** `down -v` nötig (ein `restart backend`/`up` genügt).
  Frische `docker compose up` (bzw. nach `down -v`) legt ohnehin alles an.
  **Alembic bleibt offen.**
- **Async Bon-Verarbeitung:** ~~ohne Status-Rückmeldung~~ — seit 2026-09-25 per
  `ReceiptJob` + Polling gelöst (2.12). Verbleibend: die Duplikatsprüfung beim
  Scan entfällt; BackgroundTasks sind prozessgebunden (Neustart/`--reload`
  bricht laufende Scans ab → Job wird `failed`, Bild ist weg, Nutzer muss neu
  scannen); die (kurzen) DB-Operationen laufen synchron im Event-Loop — bei der
  aktuellen Last unkritisch. Bei mehr Last: echte Queue (z. B. arq/Celery).
- **`docker compose down -v` löscht auch das Ollama-Modell** (Volume
  `ollama_models`). Seit 2026-09-25 lädt das Backend es automatisch nach (~3 GB,
  dauert) — für einen reinen DB-Reset besser gezielt nur das Postgres-Volume
  löschen: `docker compose down` + `docker volume rm yousplit_postgres_data`.
- **Namens-Cleanup `splitbill` → `yousplit` (2026-07-21):** DB-Zugangsdaten in
  `docker-compose.yml`/`database.py` geändert. Das erfordert einen **einmaligen
  DB-Reset** per `docker compose down -v` (das alte Postgres-Volume trägt noch die
  Rolle/DB `splitbill`) und danach `docker compose up --build`.
- **Kontoauszug-Parser generisch & ungetestet an echten PDFs (2026-10-02):** nur
  mit synthetischen PDFs geprüft; kein OCR; Soll/Haben-Spalten ohne Vorzeichen
  werden geraten. Dank Vorschau im UI abgefedert, siehe 2.13.
- **Ungepinnte Abhängigkeiten (Vorfall 2026-10-02):** `requirements.txt` hat keine
  Versionen. Der Image-Neubau (wegen `pdfplumber`) zog SQLAlchemy 2.1.2, das für
  `postgresql://` den Treiber `psycopg` (v3) statt `psycopg2` wählt →
  `ModuleNotFoundError: No module named 'psycopg'`, Backend startete nicht (keine
  Listen erreichbar, Daten im Postgres-Volume blieben intakt). Fix: `database.py`
  setzt `postgresql+psycopg2://` explizit, und `requirements.txt` pinnt jetzt alle
  direkten Abhängigkeiten (transitive wie pydantic/starlette bleiben frei; bei
  Bedarf mit `pip freeze` nachziehen). Updates bewusst einzeln machen.
- **Keine Authentifizierung:** Wer die Listen-UUID kennt, hat vollen Zugriff.
- **Keine automatisierten Tests** vorhanden.
- **CORS** ist fest auf `http://localhost:5173` — vor Deployment anpassen. (Lokaler
  `npm run dev` auf einem anderen Port, z. B. 5174, wird deshalb vom Backend geblockt.)
- **Docker-Hinweis (Windows-Bind-Mount):** Der Vite-Watcher im Container erkennt
  Datei-Änderungen (Config **und** Quellcode/neue Dateien) über den Windows-Mount
  nicht zuverlässig → nach Änderungen ggf. `docker compose restart frontend`.
  Analog `restart backend` nach Backend-Änderungen, falls kein Auto-Reload greift.
- **Ollama-Modell:** ~~wird nicht automatisch geladen~~ — seit 2026-09-25
  Auto-Pull durch das Backend (2.12). Der manuelle `ollama pull` (Anhang) geht
  weiterhin und ist beim allerersten Setup etwas schneller sichtbar.
- **Settlement kennt nur beteiligte Personen:** Seit Advanced Split (Roadmap 3.0
  #3) taucht auch ein reiner **Mit-Esser** im Kassensturz auf, sobald ihm eine
  Ausgabe über `splits` einen Anteil (auch 0-fähig) zuweist. Wer in **gar keiner**
  Ausgabe vorkommt (weder Zahler noch in `splits`), bleibt weiterhin unbekannt —
  eine eigenständige Teilnehmerliste je Liste gibt es noch nicht.

---

## Anhang: Betrieb & nützliche Befehle

```bash
# Alles starten (Root-Verzeichnis) — Ollama auf CPU (sicherer Default)
docker compose up --build

# Mit NVIDIA-GPU (nur bei vorhandener GPU + NVIDIA Container Toolkit):
#   entweder in .env COMPOSE_FILE auf beide Dateien setzen, oder ad hoc:
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build

# Beim ERSTEN Mal: Vision-Modell in Ollama laden (falls nicht vorhanden)
docker compose exec ollama ollama pull qwen2.5vl:3b

# Logs eines Dienstes verfolgen
docker compose logs -f backend
```

| Dienst   | URL / Port                          |
| -------- | ----------------------------------- |
| Frontend | http://localhost:5173               |
| Backend  | http://localhost:8000 (Docs: `/docs`) |
| Ollama   | http://localhost:11434              |
| Postgres | localhost:5432 (`yousplit`/`yousplit`) |

> Erster Bon-Scan nach einem (Neu-)Start ODER nach >1 Min Inaktivität ist langsam:
> Ollama lädt das Modell erst in den RAM. Seit Epic 4.0 #1 ist `OLLAMA_KEEP_ALIVE=1m`
> (Server-Schonung) — das Modell wird bewusst schnell wieder entladen. Passt zur
> asynchronen "Fire & Forget"-Verarbeitung, bei der niemand aktiv wartet.

---

_Zuletzt aktualisiert: 2026-10-02 (Kontoauszug-Import, s. 2.13: generischer PDF-Parser `bank_statement.py` (pdfplumber) + Händlerliste, Endpunkte `POST …/bank-statement/parse|import`, UI Upload→Vorschau→Import als Einzelausgaben; Komplettanalyse + Training als Zukunftspunkt 4.5 #5 vorgemerkt; 14 Parser-Tests, E2E mit Playwright, nicht an echtem Auszug getestet). Vorher: 2026-09-25 (Bugfix stille Scan-Fehler, s. 2.12: Ursache
`404 model not found` nach `down -v`; Modell-Auto-Pull `ensure_model` beim Start/
vor Scan/bei 404; Status-Rückmeldung `ReceiptJob` + Endpunkte `GET/DELETE
…/receipt-jobs` + Frontend-Polling `useReceiptJobs`/`ReceiptJobsPanel`; zentrales
`logging` statt `print`. Typecheck/Lint/Build grün, E2E mit SQLite + Ollama-Attrappe).
Vorher: 2026-07-22 (Epic 4.0 – Fundament: #1 `OLLAMA_KEEP_ALIVE=1m`
(s. 2.6/2.11); #2 asynchroner Bon-Upload via `BackgroundTasks` → sofort `202`,
fairer Split im Hintergrund `splits.fair_split`, Frontend Fire & Forget (s. 2.11,
2.3, 2.4); #3 Fundament Kontoauszüge: Modell `CategoryRule` + Schemas, 4. Tab
`BankStatementView.tsx` (PDF-Dropzone). Typecheck/Lint/Build grün. DB: `category_rules`
wird von create_all automatisch angelegt (kein Reset nötig). Backend lokal nicht
lauffähig geprüft — nur statisch. Frühere Stände: 2026-07-21 (Sprint 3.0: Roadmap 3.0 —
#1 Startseite/Dashboard `Home.tsx` + `recentLists.ts` (s. 2.10); #2 Währungen
erweitert `CurrencySelect.tsx` + `MAIN/MORE_CURRENCIES` (s. 2.8); #3 Advanced Split
`AdvancedSplitter.tsx` + reine `splitMath.ts`, neue `splits`-Spalte + Settlement
(s. 2.9, 2.2, 2.5); `SplitRatioInput.tsx` entfernt). 2026-07-21 (Sprint 2.0:
#1 – OCR-Härtetest: RECEIPT_PROMPT gehärtet + `temperature: 0`, Bon-Datum zuverlässig;
#2 – Statistiken & Charts: `recharts`, `StatisticsBoard.tsx`, Tab-Navigation
`ListTabs.tsx`, s. 2.7; #3 – Fremdwährungen: `currency.py` (Frankfurter-API),
`currency`+`exchange_rate`, EUR-Basis, s. 2.8; zusätzlich `splitbill`→`yousplit`-
Cleanup und Split-Regler-UI `SplitRatioInput.tsx`). Frühere Stände: 2026-07-20 (Roadmap
#3 – N-Personen-Kassensturz, Zahler-Dropdown, Bon-Datum + DatePicker inkl.
Bearbeiten; Roadmap #4 – Ollama GPU/CPU-Override; Roadmap #5 – Refactoring &
deutsche Kommentierung, ListView zerlegt) · Bitte bei relevanten Änderungen
fortschreiben._
