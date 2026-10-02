const API_BASE_URL = "http://localhost:8000/api";

// Vom Backend (currency.py) unterstützte Währungen – speisen die Dropdowns.
// Aufgeteilt in Haupt- und "Mehr…"-Block (Roadmap 3.0 #2): das Dropdown zeigt
// zunächst die kuratierten Hauptwährungen und klappt die europäischen
// Nebenwährungen erst auf Wunsch auf. MUSS mit MAIN_/MORE_CURRENCIES im Backend
// übereinstimmen (sonst 422 bzw. kein Kurs). EUR ist Basis-/Default-Währung.
export const MAIN_CURRENCIES = ["EUR", "USD", "CHF", "GBP"] as const;
export const MORE_CURRENCIES = [
  "SEK",
  "NOK",
  "DKK",
  "PLN",
  "CZK",
  "HUF",
  "RON",
  "BGN",
  "ISK",
] as const;
export const CURRENCIES = [...MAIN_CURRENCIES, ...MORE_CURRENCIES] as const;

// ---------- Typen (spiegeln die Pydantic-Schemas des Backends) ----------

/**
 * Advanced Split (Roadmap 3.0 #3): explizite Pro-Person-Aufteilung als
 * {Name: Betrag} in der Erfassungswährung der Ausgabe. Die Summe entspricht
 * exakt `amount`. `null` = keine feine Aufteilung → Fallback auf `split_ratio`.
 */
export type Splits = Record<string, number>;

export interface Expense {
  id: string;
  list_id: string;
  title: string;
  amount: number;
  payer_name: string;
  split_ratio: number;
  category: string;
  created_at: string; // ISO-8601, dient Sortierung + Duplikats-Prüfung
  receipt_date: string | null; // nur bei gescannten Bons (ISO YYYY-MM-DD)
  // Multi-Currency: Erfassungswährung + Tageskurs (EUR je 1 Einheit currency).
  // EUR-Betrag = amount * exchange_rate.
  currency: string;
  exchange_rate: number;
  // Advanced Split: Pro-Person-Aufteilung {Name: Betrag} oder null (Fallback).
  splits: Splits | null;
}

export interface SharedList {
  id: string;
  title: string;
  created_at: string;
  expenses: Expense[];
}

export interface ExpenseCreate {
  title: string;
  amount: number;
  payer_name: string;
  split_ratio: number;
  category?: string;
  // Bon-Datum (ISO YYYY-MM-DD): beim erzwungenen Speichern eines gescannten
  // Bons mitschicken, damit die Duplikats-Prüfung konsistent bleibt.
  receipt_date?: string | null;
  // Erfassungswährung; der Kurs wird serverseitig ermittelt (nicht mitschicken).
  currency?: string;
  // Advanced Split: Pro-Person-Aufteilung {Name: Betrag} (Summe = amount) oder null.
  splits?: Splits | null;
}

export interface ExpenseUpdate {
  title: string;
  amount: number;
  payer_name: string;
  split_ratio: number;
  category: string;
  // Ausgabendatum (ISO YYYY-MM-DD); im Bearbeiten-Formular ebenfalls anpassbar
  receipt_date?: string | null;
  currency?: string;
  // Advanced Split: Pro-Person-Aufteilung {Name: Betrag} (Summe = amount) oder null.
  splits?: Splits | null;
}

/** Die vom Backend beim Scan-Duplikat mitgelieferte KI-Analyse. */
export interface DuplicateAnalysis {
  title: string;
  amount: number;
  date: string | null; // Bon-Datum (ISO YYYY-MM-DD) oder null
  category: string;
  currency: string;
}

// ---------- Kassensturz / Settlement (N Personen) ----------

/** Eine einzelne Ausgleichszahlung: from_person zahlt an to_person. */
export interface SettlementTransaction {
  from_person: string;
  to_person: string;
  amount: number;
}

/** Saldo einer Person: net > 0 → bekommt Geld, net < 0 → schuldet Geld. */
export interface PersonBalance {
  name: string;
  paid: number;
  share: number;
  net: number;
}

export interface Settlement {
  balances: PersonBalance[];
  transactions: SettlementTransaction[];
}

/**
 * Wird geworfen, wenn das Backend ein Duplikat meldet (HTTP 409).
 * `analysis` ist nur beim Bon-Scan gesetzt – so kann das Frontend die
 * Ausgabe erzwungen speichern, ohne den Bon erneut von der KI lesen zu lassen.
 */
export class DuplicateError extends Error {
  readonly analysis?: DuplicateAnalysis;

  constructor(message: string, analysis?: DuplicateAnalysis) {
    super(message);
    this.name = "DuplicateError";
    this.analysis = analysis;
  }
}

// ---------- Helpers ----------

async function handleResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    // 204 No Content (z.B. DELETE) hat keinen Body
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }

  const body = await response.text();
  let detail: string | undefined;
  let analysis: DuplicateAnalysis | undefined;
  try {
    // FastAPI packt die Fehlerursache in {"detail": "..."};
    // beim Scan-Duplikat zusätzlich {"analysis": {...}}
    const parsed = JSON.parse(body) as {
      detail?: unknown;
      analysis?: DuplicateAnalysis;
    };
    if (typeof parsed.detail === "string") detail = parsed.detail;
    if (parsed.analysis) analysis = parsed.analysis;
  } catch {
    // Body war kein JSON — dann reicht der Statuscode
  }

  const message = detail ?? `API-Fehler ${response.status}`;
  if (response.status === 409) throw new DuplicateError(message, analysis);
  throw new Error(message);
}

// ---------- API-Funktionen ----------

export async function createList(title: string): Promise<SharedList> {
  const response = await fetch(`${API_BASE_URL}/lists`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  return handleResponse<SharedList>(response);
}

export async function getList(uuid: string): Promise<SharedList> {
  const response = await fetch(`${API_BASE_URL}/lists/${uuid}`);
  return handleResponse<SharedList>(response);
}

/** Kassensturz für N Personen: wer schuldet wem wie viel (minimal). */
export async function getSettlement(uuid: string): Promise<Settlement> {
  const response = await fetch(`${API_BASE_URL}/lists/${uuid}/settlement`);
  return handleResponse<Settlement>(response);
}

export async function addExpense(
  uuid: string,
  expenseData: ExpenseCreate,
  force = false,
): Promise<Expense> {
  const query = force ? "?force=true" : "";
  const response = await fetch(`${API_BASE_URL}/lists/${uuid}/expenses${query}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(expenseData),
  });
  return handleResponse<Expense>(response);
}

export async function updateExpense(
  uuid: string,
  expenseId: string,
  expenseData: ExpenseUpdate,
): Promise<Expense> {
  const response = await fetch(
    `${API_BASE_URL}/lists/${uuid}/expenses/${expenseId}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(expenseData),
    },
  );
  return handleResponse<Expense>(response);
}

export async function deleteExpense(
  uuid: string,
  expenseId: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/lists/${uuid}/expenses/${expenseId}`,
    { method: "DELETE" },
  );
  await handleResponse<void>(response);
}

/** Antwort des asynchronen Bon-Uploads (Fire & Forget, HTTP 202). */
export interface ReceiptUploadResult {
  status: string;
  /** ID des Status-Jobs – darüber verfolgt das Frontend den Fortschritt. */
  job_id: string;
}

/**
 * Status eines Bon-Scans im Hintergrund (Bugfix 2026-09-25). Spiegelt
 * `ReceiptJobResponse` im Backend.
 */
export type ReceiptJobStatus =
  | "processing"
  | "done"
  | "failed"
  /** Bon (Geschäft + Betrag + Datum) ist schon in der Liste – nichts angelegt. */
  | "duplicate";

export interface ReceiptJob {
  id: string;
  list_id: string;
  payer_name: string;
  filename: string | null;
  status: ReceiptJobStatus;
  /** Fortschritt 0–100 in Meilensteinen (siehe `receiptProgress.ts`). */
  progress: number;
  /** Erwartete Dauer der KI-Analyse in Sekunden (Schnitt der letzten Scans). */
  estimated_seconds: number | null;
  /** Optionaler Fortschritts-Hinweis (z. B. Modell-Download). */
  detail: string | null;
  /** Nutzerverständliche Fehlerursache bei status "failed". */
  error: string | null;
  expense_id: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Kassenbon hochladen – „Fire & Forget" (Roadmap 4.0 #2). Das Backend antwortet
 * sofort mit 202 + `job_id` und verarbeitet den Bon (OCR + fairer Split +
 * DB-Insert) im Hintergrund. Den Fortschritt liefert `getReceiptJobs`.
 */
export async function uploadReceipt(
  uuid: string,
  payerName: string,
  file: File,
): Promise<ReceiptUploadResult> {
  const formData = new FormData();
  formData.append("payer_name", payerName);
  formData.append("receipt", file);

  const response = await fetch(`${API_BASE_URL}/lists/${uuid}/receipts`, {
    method: "POST",
    // Kein Content-Type-Header: den setzt der Browser selbst
    // inklusive der multipart/form-data-Boundary
    body: formData,
  });
  return handleResponse<ReceiptUploadResult>(response);
}

/** Alle noch nicht quittierten Bon-Scans einer Liste (neueste zuerst). */
export async function getReceiptJobs(uuid: string): Promise<ReceiptJob[]> {
  const response = await fetch(`${API_BASE_URL}/lists/${uuid}/receipt-jobs`);
  return handleResponse<ReceiptJob[]>(response);
}

/**
 * „Trotzdem hinzufügen“ für einen Scan mit Status `duplicate`: legt die Ausgabe
 * aus den gespeicherten Bon-Daten an (keine erneute KI-Analyse).
 */
export async function confirmDuplicateReceipt(
  uuid: string,
  jobId: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/lists/${uuid}/receipt-jobs/${jobId}/confirm`,
    { method: "POST" },
  );
  await handleResponse<unknown>(response);
}

/** Quittiert (löscht) einen Bon-Scan-Job – erledigt oder verworfen. */
export async function dismissReceiptJob(
  uuid: string,
  jobId: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/lists/${uuid}/receipt-jobs/${jobId}`,
    { method: "DELETE" },
  );
  await handleResponse<void>(response);
}

// ---------- Kontoauszug-Import (Epic 4.0 #3) ----------

/** Eine aus dem Kontoauszug gelesene Buchung (Spiegel von `BankTransaction`). */
export interface BankTransaction {
  index: number;
  booking_date: string | null; // ISO YYYY-MM-DD
  description: string;
  /** Negativ bei Ausgaben, positiv bei Einnahmen. */
  amount: number;
  category: string | null;
  /** Anzeigename des Treffers (z. B. "Rewe") – Vorschlag für den Titel. */
  label: string | null;
  is_food: boolean;
  /** Gleicher Betrag am selben Tag existiert in der Liste bereits. */
  duplicate: boolean;
  /** Vorzeichen war im PDF nicht erkennbar (wurde angenommen). */
  sign_guessed: boolean;
}

export interface BankStatementPreview {
  transactions: BankTransaction[];
  warnings: string[];
}

export interface BankImportItem {
  title: string;
  /** Positiver Betrag in EUR. */
  amount: number;
  booking_date: string | null;
}

export interface BankImportRequest {
  payer_name: string;
  category?: string; // Default im Backend: "Lebensmittel"
  items: BankImportItem[];
}

export interface BankImportResult {
  created: number;
  total: number;
}

/**
 * Kontoauszug (PDF) hochladen und die erkannten Buchungen als Vorschau holen.
 * Es wird nichts gespeichert – erst `importBankStatement` legt Ausgaben an.
 */
export async function parseBankStatement(
  uuid: string,
  file: File,
): Promise<BankStatementPreview> {
  const formData = new FormData();
  formData.append("statement", file);

  const response = await fetch(`${API_BASE_URL}/lists/${uuid}/bank-statement/parse`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<BankStatementPreview>(response);
}

/** Die in der Vorschau bestätigten Buchungen als einzelne Ausgaben anlegen. */
export async function importBankStatement(
  uuid: string,
  payload: BankImportRequest,
): Promise<BankImportResult> {
  const response = await fetch(
    `${API_BASE_URL}/lists/${uuid}/bank-statement/import`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  return handleResponse<BankImportResult>(response);
}
