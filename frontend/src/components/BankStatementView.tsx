import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import {
  AlertTriangle,
  BookmarkPlus,
  CheckCircle2,
  ChevronDown,
  FileText,
  Landmark,
  Loader2,
  ShoppingBasket,
  Store,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import {
  classifyBankBookings,
  deleteCategoryRule,
  getCategoryRules,
  importBankStatement,
  parseBankStatement,
  saveCategoryRule,
  withReason,
} from "../api";
import type {
  BankStatementPreview,
  BankTransaction,
  CategoryRule,
  Expense,
} from "../api";
import {
  RULE_CATEGORIES,
  RULE_CATEGORY_FOOD,
  RULE_CATEGORY_IGNORE,
  ruleCategoryLabel,
} from "../categories";
import {
  applyClassifications,
  isKeywordValid,
  MIN_KEYWORD_LENGTH,
  suggestKeyword,
} from "../merchantRules";
import { formatDate, formatEuro } from "../format";
import { collectParticipants } from "../participants";
import { initialPayer, payerStorageKey } from "../payerStorage";

// Sentinel-Wert des Dropdowns für "Neue Person hinzufügen …"
const NEW_PAYER = "__new__";

const inputClass =
  "w-full rounded-xl border border-gray-300 px-4 py-3 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30";

// Buchungsarten, die als Titel nichts sagen – werden vorne abgeschnitten.
const BOOKING_TYPE_PREFIX =
  /^(basis-?lastschrift|lastschrift|kartenzahlung|girocard|debitkarte|visa|mastercard|überweisung|ueberweisung|dauerauftrag|sepa)\s+/i;

interface BankStatementViewProps {
  listId: string;
  /** Bestehende Ausgaben – daraus ergeben sich die bekannten Personen. */
  expenses: Expense[];
  /** Feste Personen der Liste. */
  members: string[];
  /** Mit dem HA-Benutzer verknüpfte Person: Zahler-Vorschlag ohne Gerätenamen. */
  linkedPayer: string | null;
  /** Nach erfolgreichem Import: ListView lädt die Liste neu. */
  onImported: () => void;
}

type Stage = "idle" | "parsing" | "preview" | "importing" | "done";

/** Ausgaben-Titel einer Buchung: Händlername (Treffer) oder gekürzter Text. */
function titleOf(transaction: BankTransaction): string {
  if (transaction.label) return transaction.label;
  const cleaned = transaction.description.replace(BOOKING_TYPE_PREFIX, "");
  return (cleaned || transaction.description).slice(0, 60);
}

/** Open "Händler merken" form of one preview row. */
interface RememberDraft {
  index: number;
  keyword: string;
  category: string;
}

/** Cent-genau summieren (Fließkomma-Drift vermeiden). */
function sumCents(values: number[]): number {
  return values.reduce((sum, value) => sum + Math.round(value * 100), 0) / 100;
}

/**
 * Kontoauszug-Import (Epic 4.0 #3): PDF hochladen → Vorschau der erkannten
 * Lebensmittel-Buchungen → bestätigte Buchungen werden einzeln als Ausgaben
 * angelegt (fair aufgeteilt, Backend: `bank-statement/import`).
 *
 * Die Erkennung ist generisch (kein bankspezifisches Layout) – deshalb gibt es
 * immer die Vorschau: Treffer lassen sich abwählen, übersehene Buchungen unter
 * „Weitere Ausgaben“ nachträglich anhaken.
 */
function BankStatementView({
  listId,
  expenses,
  members,
  linkedPayer,
  onImported,
}: BankStatementViewProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [stage, setStage] = useState<Stage>("idle");
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<BankStatementPreview | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  // Bumped by every reclassification, new file and reset. A reclassification
  // only applies its answer if it is still the latest, so a slow response
  // never lands on another statement or overwrites a newer one.
  const refreshSeq = useRef(0);
  const [showOthers, setShowOthers] = useState(false);
  const [result, setResult] = useState<{
    created: number;
    total: number;
  } | null>(null);

  // Remembered merchants of the list (server side, shared by all devices).
  const [rules, setRules] = useState<CategoryRule[]>([]);
  const [showRules, setShowRules] = useState(false);
  const [rulesError, setRulesError] = useState<string | null>(null);
  const [remember, setRemember] = useState<RememberDraft | null>(null);
  const [rememberBusy, setRememberBusy] = useState(false);
  const [rememberError, setRememberError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getCategoryRules(listId)
      .then((loaded) => {
        if (!cancelled) setRules(loaded);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setRulesError(
            withReason("Gemerkte Händler konnten nicht geladen werden", err),
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [listId]);

  // Bekannte Personen der Liste (Zahler und Mit-Esser, wie im Kassensturz)
  const knownPersons = useMemo(
    () => collectParticipants(expenses, members),
    [expenses, members],
  );

  const [payerName, setPayerName] = useState<string>(() =>
    initialPayer(listId, linkedPayer),
  );
  // Freitext nur, wenn es noch niemanden zur Auswahl gibt; sonst Dropdown mit
  // Platzhalter "Bitte wählen …" (kein stilles Raten, wer bezahlt hat).
  const [addingNewPayer, setAddingNewPayer] = useState<boolean>(
    () => !initialPayer(listId, linkedPayer) && knownPersons.length === 0,
  );

  // Dropdown-Optionen: Bekannte plus ein evtl. gemerkter Gerätename.
  const payerOptions = useMemo(() => {
    const options = [...knownPersons];
    const current = payerName.trim();
    if (current && !addingNewPayer && !options.includes(current)) {
      options.push(current);
    }
    return options;
  }, [knownPersons, payerName, addingNewPayer]);

  // Nur Ausgaben (negativ) sind relevant; Einnahmen werden nur gezählt.
  const { foodRows, otherRows, incomeCount } = useMemo(() => {
    const all = preview?.transactions ?? [];
    return {
      foodRows: all.filter((t) => t.amount < 0 && t.is_food),
      otherRows: all.filter((t) => t.amount < 0 && !t.is_food),
      incomeCount: all.filter((t) => t.amount >= 0).length,
    };
  }, [preview]);

  const selectedRows = useMemo(
    () => [...foodRows, ...otherRows].filter((t) => selected.has(t.index)),
    [foodRows, otherRows, selected],
  );
  const selectedTotal = sumCents(selectedRows.map((t) => Math.abs(t.amount)));

  // Nur PDFs akzeptieren – über MIME-Typ ODER Dateiendung (mobile Browser setzen
  // den Typ nicht immer zuverlässig).
  function isPdf(file: File): boolean {
    return (
      file.type === "application/pdf" ||
      file.name.toLowerCase().endsWith(".pdf")
    );
  }

  async function handleFile(file: File) {
    if (!isPdf(file)) {
      setError("Bitte eine PDF-Datei auswählen (.pdf).");
      return;
    }
    setError(null);
    setFileName(file.name);
    setStage("parsing");
    refreshSeq.current += 1;
    try {
      const parsed = await parseBankStatement(listId, file);
      setPreview(parsed);
      // Vorauswahl: erkannte Lebensmittel, aber nichts, was es schon gibt.
      setSelected(
        new Set(
          parsed.transactions
            .filter((t) => t.amount < 0 && t.is_food && !t.duplicate)
            .map((t) => t.index),
        ),
      );
      setShowOthers(false);
      setStage("preview");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Der Kontoauszug konnte nicht gelesen werden.",
      );
      setStage("idle");
    }
  }

  function reset() {
    refreshSeq.current += 1;
    setRemember(null);
    setRememberError(null);
    setStage("idle");
    setPreview(null);
    setSelected(new Set());
    setFileName(null);
    setError(null);
    setResult(null);
  }

  function toggle(index: number) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  function setAllFood(checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      for (const row of foodRows) {
        if (checked) next.add(row.index);
        else next.delete(row.index);
      }
      return next;
    });
  }

  // ---------- Remembered merchants ----------

  /** The default category is what the user just decided for this row. */
  function openRemember(transaction: BankTransaction) {
    const checked = selected.has(transaction.index);
    const category =
      !checked && transaction.is_food ? RULE_CATEGORY_IGNORE : RULE_CATEGORY_FOOD;
    setRememberError(null);
    setRemember({
      index: transaction.index,
      keyword: suggestKeyword(transaction.description, transaction.label),
      category,
    });
  }

  /**
   * Classify the open preview again in the backend, so every row with the
   * same merchant follows the changed rules at once. The backend owns the
   * matching (folding, rule precedence, longest keyword); a local copy would
   * drift apart from it.
   *
   * Both updates are functional: ticks the user sets while the request runs
   * stay, and the result is dropped if the preview changed meanwhile (new
   * file, reset or a newer reclassification).
   */
  async function refreshPreview(): Promise<void> {
    const snapshot = preview;
    if (!snapshot) return;
    const expenseRows = snapshot.transactions.filter((t) => t.amount < 0);
    if (expenseRows.length === 0) return;
    const seq = ++refreshSeq.current;
    const results = await classifyBankBookings(
      listId,
      expenseRows.map((t) => t.description),
    );
    if (seq !== refreshSeq.current) return;
    // Only this function changes the transactions of an open preview, and
    // every older reclassification was dropped above, so the snapshot is
    // still the current preview (checked again in the updater).
    const { transactions } = applyClassifications(
      snapshot.transactions,
      expenseRows,
      results,
      new Set(),
    );
    setPreview((prev) =>
      prev === snapshot ? { ...prev, transactions } : prev,
    );
    setSelected(
      (prev) =>
        applyClassifications(snapshot.transactions, expenseRows, results, prev)
          .selected,
    );
  }

  async function handleRememberSave() {
    if (!remember || !isKeywordValid(remember.keyword)) return;
    setRememberBusy(true);
    setRememberError(null);
    let saved: CategoryRule;
    try {
      saved = await saveCategoryRule(listId, {
        recipient_keyword: remember.keyword.trim(),
        category: remember.category,
      });
    } catch (err) {
      setRememberError(withReason("Händler konnte nicht gemerkt werden", err));
      setRememberBusy(false);
      return;
    }
    setRules((current) =>
      [...current.filter((rule) => rule.id !== saved.id), saved].sort((a, b) =>
        a.recipient_keyword.localeCompare(b.recipient_keyword, "de"),
      ),
    );
    try {
      await refreshPreview();
      setRemember(null);
    } catch (err) {
      setRememberError(
        withReason("Händler gemerkt, aber die Vorschau ist nicht aktuell", err),
      );
    } finally {
      setRememberBusy(false);
    }
  }

  async function handleRuleDelete(rule: CategoryRule) {
    setRulesError(null);
    try {
      await deleteCategoryRule(listId, rule.id);
    } catch (err) {
      setRulesError(withReason("Händler konnte nicht entfernt werden", err));
      return;
    }
    setRules((current) => current.filter((r) => r.id !== rule.id));
    try {
      await refreshPreview();
    } catch (err) {
      setRulesError(
        withReason("Händler entfernt, aber die Vorschau ist nicht aktuell", err),
      );
    }
  }

  function handlePayerSelect(value: string) {
    if (value === NEW_PAYER) {
      setAddingNewPayer(true);
      setPayerName("");
      return;
    }
    setAddingNewPayer(false);
    setPayerName(value);
  }

  async function handleImport() {
    const payer = payerName.trim();
    if (!payer) {
      setError("Bitte angeben, wer bezahlt hat.");
      return;
    }
    if (selectedRows.length === 0) return;

    setError(null);
    setStage("importing");
    try {
      const response = await importBankStatement(listId, {
        payer_name: payer,
        items: selectedRows.map((t) => ({
          title: titleOf(t),
          amount: Math.abs(t.amount),
          booking_date: t.booking_date,
        })),
      });
      localStorage.setItem(payerStorageKey(listId), payer);
      setPayerName(payer);
      setAddingNewPayer(false);
      setResult(response);
      setStage("done");
      onImported();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Der Import ist fehlgeschlagen.",
      );
      setStage("preview");
    }
  }

  // ---------- Datei-Auswahl (Dropzone) ----------

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // Input leeren, damit dieselbe Datei direkt nochmal gewählt werden kann.
    event.target.value = "";
    if (file) void handleFile(file);
  }

  function handleDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setDragActive(false);
    const file = event.dataTransfer.files?.[0];
    if (file) void handleFile(file);
  }

  function handleDragOver(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setDragActive(true);
  }

  function handleDragLeave(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setDragActive(false);
  }

  // ---------- Darstellung einer Buchungszeile ----------

  function renderRow(transaction: BankTransaction) {
    const checked = selected.has(transaction.index);
    // Offer to remember the merchant where the detection did not help: no hit
    // at all, or the user overrode it (picked a non-food row, dropped a food row).
    const canRemember =
      stage === "preview" &&
      (transaction.category === null || checked !== transaction.is_food);
    const draft = remember?.index === transaction.index ? remember : null;
    return (
      <li key={transaction.index}>
        <label
          className={`flex cursor-pointer items-start gap-3 rounded-xl border px-3 py-3 transition ${
            checked
              ? "border-emerald-200 bg-emerald-50/60"
              : "border-gray-100 bg-white hover:bg-gray-50"
          }`}
        >
          <input
            type="checkbox"
            checked={checked}
            onChange={() => toggle(transaction.index)}
            className="mt-1 h-4 w-4 shrink-0 accent-emerald-600"
          />
          <span className="min-w-0 flex-1">
            <span className="flex items-baseline justify-between gap-3">
              <span className="truncate text-sm font-semibold text-gray-900">
                {titleOf(transaction)}
              </span>
              <span className="shrink-0 text-sm font-semibold tabular-nums text-gray-900">
                {formatEuro(Math.abs(transaction.amount))}
              </span>
            </span>
            <span className="mt-0.5 line-clamp-2 text-xs text-gray-500">
              {transaction.booking_date
                ? `${formatDate(transaction.booking_date)} · `
                : ""}
              {transaction.description}
            </span>
            {transaction.duplicate && (
              <span className="mt-1 inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                Gleicher Betrag am selben Tag existiert schon
              </span>
            )}
          </span>
        </label>
        {canRemember && !draft && (
          <button
            type="button"
            onClick={() => openRemember(transaction)}
            className="ml-10 mt-1 inline-flex items-center gap-1 text-xs font-medium text-emerald-700 hover:underline"
          >
            <BookmarkPlus className="h-3.5 w-3.5" />
            Händler merken
          </button>
        )}
        {draft && renderRememberForm(draft)}
      </li>
    );
  }

  function renderRememberForm(draft: RememberDraft) {
    const valid = isKeywordValid(draft.keyword);
    const fieldClass =
      "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30";
    return (
      <div className="mt-2 rounded-xl border border-emerald-100 bg-emerald-50/40 px-3 py-3 sm:ml-7">
        <label
          htmlFor={`remember-keyword-${draft.index}`}
          className="mb-1 block text-xs font-medium text-gray-700"
        >
          Stichwort (Händler oder Empfänger)
        </label>
        <input
          id={`remember-keyword-${draft.index}`}
          type="text"
          value={draft.keyword}
          onChange={(event) =>
            setRemember({ ...draft, keyword: event.target.value })
          }
          maxLength={200}
          placeholder="z. B. Hans Meier e.K."
          className={fieldClass}
        />
        <label
          htmlFor={`remember-category-${draft.index}`}
          className="mb-1 mt-2 block text-xs font-medium text-gray-700"
        >
          Buchungen mit diesem Stichwort sind
        </label>
        <select
          id={`remember-category-${draft.index}`}
          value={draft.category}
          onChange={(event) =>
            setRemember({ ...draft, category: event.target.value })
          }
          className={fieldClass}
        >
          {RULE_CATEGORIES.map((category) => (
            <option key={category} value={category}>
              {ruleCategoryLabel(category)}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-gray-400">
          {valid
            ? "Gilt ab jetzt für diese Liste, auch für die übrigen Buchungen dieses Auszugs."
            : `Mindestens ${MIN_KEYWORD_LENGTH} Buchstaben oder Ziffern.`}
        </p>
        {rememberError && (
          <p className="mt-1 text-xs text-red-600">{rememberError}</p>
        )}
        <div className="mt-2 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => {
              setRemember(null);
              setRememberError(null);
            }}
            disabled={rememberBusy}
            className="rounded-lg px-3 py-1.5 text-xs font-semibold text-gray-600 transition hover:bg-gray-100 disabled:opacity-50"
          >
            Abbrechen
          </button>
          <button
            type="button"
            onClick={() => void handleRememberSave()}
            disabled={rememberBusy || !valid}
            className="flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-gray-300"
          >
            {rememberBusy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Merken
          </button>
        </div>
      </div>
    );
  }

  function renderRules() {
    return (
      <div className="mt-5">
        <button
          type="button"
          onClick={() => setShowRules((open) => !open)}
          className="flex w-full items-center justify-between rounded-xl border border-gray-200 px-4 py-3 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
        >
          <span className="flex items-center gap-2">
            <Store className="h-4 w-4 text-gray-400" />
            Gemerkte Händler ({rules.length})
          </span>
          <ChevronDown
            className={`h-4 w-4 text-gray-400 transition ${
              showRules ? "rotate-180" : ""
            }`}
          />
        </button>
        {showRules &&
          (rules.length === 0 ? (
            <p className="mt-2 rounded-xl bg-gray-50 px-4 py-3 text-xs text-gray-500">
              Noch keine Händler gemerkt. In der Vorschau kannst du bei
              unerkannten oder falsch erkannten Buchungen „Händler merken“
              wählen.
            </p>
          ) : (
            <ul className="mt-2 space-y-1">
              {rules.map((rule) => (
                <li
                  key={rule.id}
                  className="flex items-center gap-3 rounded-xl border border-gray-100 px-3 py-2"
                >
                  <span className="min-w-0 flex-1 truncate text-sm text-gray-900">
                    {rule.recipient_keyword}
                  </span>
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                      rule.category === RULE_CATEGORY_FOOD
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {ruleCategoryLabel(rule.category)}
                  </span>
                  <button
                    type="button"
                    onClick={() => void handleRuleDelete(rule)}
                    disabled={stage === "importing"}
                    aria-label={`„${rule.recipient_keyword}“ vergessen`}
                    title="Vergessen"
                    className="shrink-0 rounded-lg p-1 text-gray-400 transition hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          ))}
        {rulesError && <p className="mt-2 text-xs text-red-600">{rulesError}</p>}
      </div>
    );
  }

  const allFoodSelected =
    foodRows.length > 0 && foodRows.every((t) => selected.has(t.index));

  return (
    <div className="mt-6 rounded-xl border border-gray-100 bg-white p-5 shadow-sm sm:p-6">
      <h2 className="mb-1 flex items-center gap-2 text-lg font-semibold text-gray-900">
        <Landmark className="h-5 w-5 text-emerald-600" />
        Kontoauszug importieren
      </h2>

      {/* ---------- 1) Upload ---------- */}
      {(stage === "idle" || stage === "parsing") && (
        <>
          <p className="mb-4 text-sm text-gray-500">
            Lade einen Kontoauszug als PDF hoch. YouSplit sucht darin deine
            Lebensmitteleinkäufe (REWE, EDEKA, ALDI, LIDL …) und zeigt sie dir
            vorab zur Kontrolle. Das PDF wird nicht gespeichert.
          </p>

          {stage === "parsing" ? (
            <div className="flex flex-col items-center gap-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-10 text-center">
              <Loader2 className="h-6 w-6 animate-spin text-emerald-600" />
              <span className="text-sm font-medium text-gray-700">
                Kontoauszug wird gelesen …
              </span>
              {fileName && (
                <span className="max-w-full truncate text-xs text-gray-400">
                  {fileName}
                </span>
              )}
            </div>
          ) : (
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              className={`flex w-full flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-4 py-10 text-center transition ${
                dragActive
                  ? "border-emerald-500 bg-emerald-50"
                  : "border-gray-300 bg-gray-50 hover:border-emerald-400 hover:bg-emerald-50/50"
              }`}
            >
              <span className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
                <UploadCloud className="h-6 w-6" />
              </span>
              <span className="text-sm font-semibold text-gray-700">
                PDF hierher ziehen oder klicken zum Auswählen
              </span>
              <span className="text-xs text-gray-400">
                Nur PDF-Dateien (.pdf)
              </span>
            </button>
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={handleInputChange}
          />
          {renderRules()}
        </>
      )}

      {/* ---------- 2) Vorschau ---------- */}
      {(stage === "preview" || stage === "importing") && preview && (
        <>
          <div className="mb-4 flex items-center gap-2 rounded-xl bg-gray-50 px-4 py-3 text-sm text-gray-700">
            <FileText className="h-5 w-5 shrink-0 text-gray-400" />
            <span className="truncate">{fileName}</span>
            <button
              type="button"
              onClick={reset}
              disabled={stage === "importing"}
              aria-label="Anderen Auszug wählen"
              className="ml-auto shrink-0 rounded-lg p-1 text-gray-400 transition hover:bg-gray-200 hover:text-gray-600 disabled:opacity-50"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {preview.warnings.length > 0 && (
            <div className="mb-4 flex gap-2 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <ul className="space-y-1">
                {preview.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="mb-2 flex items-center justify-between gap-3">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
              <ShoppingBasket className="h-4 w-4 text-emerald-600" />
              Erkannte Lebensmittel ({foodRows.length})
            </h3>
            {foodRows.length > 0 && (
              <button
                type="button"
                onClick={() => setAllFood(!allFoodSelected)}
                className="text-xs font-medium text-emerald-700 hover:underline"
              >
                {allFoodSelected ? "Keine auswählen" : "Alle auswählen"}
              </button>
            )}
          </div>

          {foodRows.length === 0 ? (
            <p className="rounded-xl bg-gray-50 px-4 py-4 text-sm text-gray-500">
              Keine Lebensmitteleinkäufe erkannt. Unter „Weitere Ausgaben“
              kannst du Buchungen von Hand auswählen.
            </p>
          ) : (
            <ul className="space-y-2">{foodRows.map(renderRow)}</ul>
          )}

          {otherRows.length > 0 && (
            <div className="mt-4">
              <button
                type="button"
                onClick={() => setShowOthers((open) => !open)}
                className="flex w-full items-center justify-between rounded-xl border border-gray-200 px-4 py-3 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
              >
                <span>Weitere Ausgaben ({otherRows.length})</span>
                <ChevronDown
                  className={`h-4 w-4 text-gray-400 transition ${
                    showOthers ? "rotate-180" : ""
                  }`}
                />
              </button>
              {showOthers && (
                <>
                  <p className="mt-2 text-xs text-gray-400">
                    Hier angehakte Buchungen werden ebenfalls als Lebensmittel
                    angelegt.
                  </p>
                  <ul className="mt-2 space-y-2">{otherRows.map(renderRow)}</ul>
                </>
              )}
            </div>
          )}

          {incomeCount > 0 && (
            <p className="mt-3 text-xs text-gray-400">
              {incomeCount === 1
                ? "1 Einnahme im Auszug wird ignoriert."
                : `${incomeCount} Einnahmen im Auszug werden ignoriert.`}
            </p>
          )}

          {renderRules()}

          {/* Zahler: die Ausgaben werden fair auf alle Personen der Liste geteilt */}
          <div className="mt-5">
            <label
              htmlFor="bank-payer"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              Wer hat bezahlt?
            </label>
            {payerOptions.length > 0 && !addingNewPayer ? (
              <select
                id="bank-payer"
                value={payerName}
                onChange={(event) => handlePayerSelect(event.target.value)}
                className={`${inputClass} bg-white`}
              >
                {!payerName.trim() && (
                  <option value="" disabled>
                    Bitte wählen …
                  </option>
                )}
                {payerOptions.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
                <option value={NEW_PAYER}>Neue Person hinzufügen …</option>
              </select>
            ) : (
              <input
                id="bank-payer"
                type="text"
                value={payerName}
                onChange={(event) => setPayerName(event.target.value)}
                placeholder="z. B. Max"
                maxLength={100}
                className={inputClass}
              />
            )}
            <p className="mt-1 text-xs text-gray-400">
              Jede Buchung wird zu gleichen Teilen auf alle Personen der Liste
              aufgeteilt.
            </p>
          </div>

          <button
            type="button"
            onClick={() => void handleImport()}
            disabled={
              stage === "importing" ||
              selectedRows.length === 0 ||
              !payerName.trim()
            }
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-gray-300"
          >
            {stage === "importing" && (
              <Loader2 className="h-4 w-4 animate-spin" />
            )}
            {selectedRows.length === 0
              ? "Keine Buchung ausgewählt"
              : `${selectedRows.length} Buchung${selectedRows.length === 1 ? "" : "en"} anlegen (${formatEuro(selectedTotal)})`}
          </button>
        </>
      )}

      {/* ---------- 3) Fertig ---------- */}
      {stage === "done" && result && (
        <div className="mt-4 text-center">
          <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-600" />
          <p className="mt-3 text-base font-semibold text-gray-900">
            {result.created} Ausgabe{result.created === 1 ? "" : "n"} angelegt
          </p>
          <p className="mt-1 text-sm text-gray-500">
            Gesamt {formatEuro(result.total)} – du findest sie im Tab „Ausgaben“
            und im Kassensturz.
          </p>
          <button
            type="button"
            onClick={reset}
            className="mt-5 rounded-xl border border-gray-300 px-4 py-2.5 text-sm font-semibold text-gray-700 transition hover:bg-gray-50"
          >
            Weiteren Auszug importieren
          </button>
        </div>
      )}

      {error && (
        <p className="mt-3 text-center text-sm text-red-600">{error}</p>
      )}
    </div>
  );
}

export default BankStatementView;
