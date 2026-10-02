import { useMemo, useRef, useState } from "react";
import type { ChangeEvent, FormEvent, RefObject } from "react";
import { Camera, Loader2, Plus, X } from "lucide-react";
import { addExpense, DuplicateError, uploadReceipt } from "../api";
import type { Expense } from "../api";
import { formatEuro } from "../format";
import { payerStorageKey } from "../payerStorage";
import AdvancedSplitter from "./AdvancedSplitter";
import type { AdvancedSplitterHandle } from "./AdvancedSplitter";
import ConfirmDialog from "./ConfirmDialog";
import CurrencySelect from "./CurrencySelect";
import DatePicker from "./DatePicker";

// Sentinel-Wert des Dropdowns für "Neue Person hinzufügen …"
const NEW_PAYER = "__new__";

// Heutiges Datum als ISO "YYYY-MM-DD" (lokale Komponenten, keine Zeitzonen-Drift)
const todayIso = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
};

// Geteiltes Styling für Text-/Auswahlfelder – vermeidet Wiederholung im JSX
const inputClass =
  "w-full rounded-xl border border-gray-300 px-4 py-3 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30";

/** Offene Duplikats-Warnung inkl. der Aktion, die "Trotzdem speichern" ausführt. */
interface DuplicatePrompt {
  message: string;
  onConfirm: () => Promise<void>;
}

interface ExpenseFormProps {
  listId: string;
  /** Alle Ausgaben der Liste – speisen das Zahler-Dropdown (bekannte Zahler). */
  expenses: Expense[];
  /** Wird nach erfolgreichem Anlegen/Scannen mit der neuen Ausgabe aufgerufen. */
  onExpenseAdded: (expense: Expense) => void;
  /**
   * Wird aufgerufen, sobald ein Bon angenommen wurde (HTTP 202) – ListView
   * startet daraufhin das Status-Polling (siehe useReceiptJobs).
   */
  onReceiptQueued: () => void;
  /** Ref aufs Titelfeld, damit der Empty-State-CTA hierher fokussieren kann. */
  titleInputRef: RefObject<HTMLInputElement | null>;
}

/**
 * Formular zum Anlegen einer Ausgabe – manuell oder per Kassenbon-Scan.
 *
 * Kapselt das komplette "Ausgabe hinzufügen"-Feature: Eingabefelder, Datum
 * (DatePicker), Zahler-Dropdown mit "Neue Person" und Geräte-Erkennung
 * (localStorage), Split-Slider (Eigenanteil des Zahlers), Bon-Scan sowie die
 * Duplikats-Warnung mit "Trotzdem speichern". Nach außen kommuniziert es nur
 * über onExpenseAdded – die restliche Zustandsverwaltung bleibt hier gekapselt.
 */
function ExpenseForm({
  listId,
  expenses,
  onExpenseAdded,
  onReceiptQueued,
  titleInputRef,
}: ExpenseFormProps) {
  const [title, setTitle] = useState("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("EUR");
  const [expenseDate, setExpenseDate] = useState(todayIso);
  // Advanced Splitter: verwaltet seinen Zustand selbst; wir lesen das Ergebnis
  // beim Speichern per Ref und erzwingen nach dem Anlegen einen Reset via key.
  const splitterRef = useRef<AdvancedSplitterHandle>(null);
  const [splitterKey, setSplitterKey] = useState(0);

  // Zahler + Geräte-Erkennung: initial der auf diesem Gerät gemerkte Name.
  const [payerName, setPayerName] = useState<string>(
    () => localStorage.getItem(payerStorageKey(listId))?.trim() ?? "",
  );
  // Ohne gemerkten Namen direkt im Freitext-Modus ("Neue Person") starten.
  const [addingNewPayer, setAddingNewPayer] = useState<boolean>(
    () => !localStorage.getItem(payerStorageKey(listId))?.trim(),
  );
  // Listenwechsel ohne Remount: gemerkten Namen der neuen Liste übernehmen.
  // setState während des Renderns ist Reacts empfohlener Weg dafür (statt Effekt).
  const [knownListId, setKnownListId] = useState(listId);
  if (listId !== knownListId) {
    setKnownListId(listId);
    const stored = localStorage.getItem(payerStorageKey(listId))?.trim();
    setPayerName(stored ?? "");
    setAddingNewPayer(!stored);
  }

  const [saving, setSaving] = useState(false);
  // Kurzer Hinweis, solange der Bon hochgeladen wird. Den weiteren Verlauf
  // (Verarbeitung, Fehler) zeigt ReceiptJobsPanel in der ListView.
  const [scanNotice, setScanNotice] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState<DuplicatePrompt | null>(null);
  const [duplicateBusy, setDuplicateBusy] = useState(false);

  // Unsichtbarer Datei-Input (öffnet mobil die Kamera) und Freitext-Zahlerfeld
  const fileInputRef = useRef<HTMLInputElement>(null);
  const newPayerInputRef = useRef<HTMLInputElement>(null);

  // Bekannte Zahler: alle Personen mit mind. einer Ausgabe, in Reihenfolge des
  // ersten Auftretens.
  const knownPayers = useMemo(() => {
    const seen = new Set<string>();
    const names: string[] = [];
    for (const expense of expenses) {
      if (!seen.has(expense.payer_name)) {
        seen.add(expense.payer_name);
        names.push(expense.payer_name);
      }
    }
    return names;
  }, [expenses]);

  // Dropdown-Optionen: bekannte Zahler plus – falls noch nicht enthalten – der
  // aktuell gewählte Name (z. B. der gemerkte Gerätename ohne eigene Ausgabe),
  // damit die <select>-value stets zu einer Option passt.
  const payerOptions = useMemo(() => {
    const options = [...knownPayers];
    const current = payerName.trim();
    if (current && !addingNewPayer && !options.includes(current)) {
      options.push(current);
    }
    return options;
  }, [knownPayers, payerName, addingNewPayer]);

  // Betrag als Zahl fürs Splitter-Preview/-Ergebnis (0, solange leer/ungültig).
  const parsedAmountValue = Number.parseFloat(amount.replace(",", "."));
  const splitAmount =
    Number.isFinite(parsedAmountValue) && parsedAmountValue > 0
      ? parsedAmountValue
      : 0;

  // Teilnehmer des Splitters: alle bekannten Zahler plus der aktuell gewählte
  // Zahler (auch ein noch neuer Name) – so ist der Zahler immer dabei.
  const splitParticipants = useMemo(() => {
    const names = [...knownPayers];
    const current = payerName.trim();
    if (current && !names.includes(current)) names.push(current);
    return names;
  }, [knownPayers, payerName]);

  function resetForm() {
    // Zahler bewusst stehen lassen – oft trägt dieselbe Person mehrere Ausgaben ein
    setTitle("");
    setAmount("");
    // Splitter auf faire Standardaufteilung zurücksetzen (Remount via key)
    setSplitterKey((key) => key + 1);
    setExpenseDate(todayIso());
    // Hinweis vom letzten Bon-Upload verwerfen (wird bei Bedarf neu gesetzt)
    setScanNotice(null);
  }

  // Geräte-Erkennung: gewählten/erstellten Namen für diese Liste merken.
  function rememberPayer(name: string) {
    const trimmed = name.trim();
    if (trimmed) localStorage.setItem(payerStorageKey(listId), trimmed);
  }

  // Nach dem Speichern: Namen merken, auf den getrimmten Wert normalisieren
  // (passt dann zur Dropdown-Option) und den Freitext-Modus verlassen.
  function commitPayer(name: string) {
    const trimmed = name.trim();
    rememberPayer(trimmed);
    setPayerName(trimmed);
    setAddingNewPayer(false);
  }

  function handlePayerSelect(value: string) {
    if (value === NEW_PAYER) {
      setAddingNewPayer(true);
      setPayerName("");
      // Nach dem Umschalten aufs Freitextfeld dorthin fokussieren
      requestAnimationFrame(() => newPayerInputRef.current?.focus());
      return;
    }
    setAddingNewPayer(false);
    setPayerName(value);
    rememberPayer(value);
  }

  // Zurück von der Freitext-Eingabe zur Auswahl (nur mit bekannten Zahlern)
  function cancelNewPayer() {
    setAddingNewPayer(false);
    setPayerName(knownPayers[0] ?? "");
  }

  async function handleAddExpense(event: FormEvent) {
    event.preventDefault();

    // Komma als Dezimaltrenner erlauben ("4,50" -> 4.50)
    const parsedAmount = Number.parseFloat(amount.replace(",", "."));
    if (
      !title.trim() ||
      !payerName.trim() ||
      Number.isNaN(parsedAmount) ||
      parsedAmount <= 0
    ) {
      setFormError("Bitte Titel, Betrag (> 0) und Zahler angeben.");
      return;
    }

    // Aufteilung aus dem Splitter lesen: {Name: Betrag} + abgeleiteter Eigenanteil
    // des Zahlers (split_ratio bleibt als Fallback kohärent).
    const split = splitterRef.current?.getResult();
    const data = {
      title: title.trim(),
      amount: parsedAmount,
      payer_name: payerName.trim(),
      split_ratio: split?.splitRatio ?? 0.5,
      receipt_date: expenseDate,
      currency,
      splits: split?.splits ?? null,
    };

    setSaving(true);
    setFormError(null);
    try {
      onExpenseAdded(await addExpense(listId, data));
      commitPayer(data.payer_name);
      resetForm();
    } catch (error) {
      if (error instanceof DuplicateError) {
        // Speichern anhalten und Warnung zeigen; "Trotzdem speichern" erzwingt es
        setDuplicate({
          message: `Eine Ausgabe über ${formatEuro(parsedAmount)} am selben Tag existiert bereits. Trotzdem speichern?`,
          onConfirm: async () => {
            onExpenseAdded(await addExpense(listId, data, true));
            commitPayer(data.payer_name);
            resetForm();
          },
        });
      } else {
        setFormError("Ausgabe konnte nicht gespeichert werden.");
      }
    } finally {
      setSaving(false);
    }
  }

  function handleScanClick() {
    // Das Backend braucht den Zahler, bevor die Datei ausgewählt wird
    if (!payerName.trim()) {
      setFormError('Bitte zuerst bei "Wer hat bezahlt?" einen Namen eintragen.');
      return;
    }
    setFormError(null);
    fileInputRef.current?.click();
  }

  // Fire & Forget (Roadmap 4.0 #2): Der Bon wird NICHT blockierend analysiert.
  // Nach dem Upload (202 + job_id) übernimmt ReceiptJobsPanel die Anzeige: es
  // zeigt "wird verarbeitet", fügt die fertige Ausgabe automatisch ein oder
  // meldet einen Fehler (Bugfix 2026-09-25 – vorher scheiterten Scans still).
  function handleReceiptSelected(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // Input leeren, damit derselbe Bon direkt nochmal gewählt werden kann
    event.target.value = "";
    if (!file) return;

    const payer = payerName.trim();
    setFormError(null);
    // Zahler auf dem Gerät merken/normalisieren (auch wenn die App gleich zugeht)
    commitPayer(payer);

    // resetForm() verwirft u. a. einen alten Hinweis – daher DANACH setzen.
    resetForm();
    setScanNotice("Beleg wird hochgeladen …");

    uploadReceipt(listId, payer, file)
      .then(() => {
        setScanNotice(null);
        onReceiptQueued();
      })
      .catch((error: unknown) => {
        setScanNotice(null);
        const reason = error instanceof Error ? error.message : "";
        setFormError(
          `Der Beleg-Upload ist fehlgeschlagen${reason ? `: ${reason}` : ""}. Läuft das Backend?`,
        );
      });
  }

  async function confirmDuplicate() {
    if (!duplicate) return;
    setDuplicateBusy(true);
    try {
      await duplicate.onConfirm();
      setDuplicate(null);
    } catch {
      setDuplicate(null);
      setFormError("Speichern trotz Duplikat fehlgeschlagen.");
    } finally {
      setDuplicateBusy(false);
    }
  }

  return (
    <>
      <form
        onSubmit={handleAddExpense}
        className="mt-6 rounded-xl border border-gray-100 bg-white p-5 shadow-sm sm:p-6"
      >
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
          <Plus className="h-5 w-5 text-emerald-600" />
          Neue Ausgabe
        </h2>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label
              htmlFor="expense-title"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              Was wurde gekauft?
            </label>
            <input
              id="expense-title"
              ref={titleInputRef}
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder='z.B. "Pizza"'
              maxLength={200}
              className={inputClass}
            />
          </div>

          <div>
            <label
              htmlFor="expense-amount"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              Betrag
            </label>
            <div className="flex gap-2">
              <input
                id="expense-amount"
                type="text"
                inputMode="decimal"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                placeholder="24,50"
                className={`${inputClass} flex-1`}
              />
              {/* Währungswahl (Multi-Currency): der Kurs wird serverseitig ermittelt */}
              <CurrencySelect value={currency} onChange={setCurrency} />
            </div>
          </div>

          <div>
            <label
              htmlFor="expense-date"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              Datum
            </label>
            <DatePicker
              id="expense-date"
              value={expenseDate}
              onChange={setExpenseDate}
            />
          </div>

          <div className="sm:col-span-2">
            <label
              htmlFor="expense-payer"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              Wer hat bezahlt?
            </label>
            {payerOptions.length > 0 && !addingNewPayer ? (
              <select
                id="expense-payer"
                value={payerName}
                onChange={(event) => handlePayerSelect(event.target.value)}
                className={`${inputClass} bg-white`}
              >
                {payerOptions.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
                <option value={NEW_PAYER}>Neue Person hinzufügen …</option>
              </select>
            ) : (
              <div className="flex gap-2">
                <input
                  id="expense-payer"
                  ref={newPayerInputRef}
                  type="text"
                  value={payerName}
                  onChange={(event) => setPayerName(event.target.value)}
                  placeholder="z.B. Kevin"
                  maxLength={100}
                  className={inputClass}
                />
                {/* Zurück zur Auswahl nur anbieten, wenn es Bekannte gibt */}
                {knownPayers.length > 0 && (
                  <button
                    type="button"
                    onClick={cancelNewPayer}
                    aria-label="Zurück zur Auswahl"
                    className="shrink-0 rounded-xl border border-gray-300 px-3 text-gray-400 transition hover:bg-gray-50 hover:text-gray-600"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* ---------- Advanced Split: Aufteilung über alle Teilnehmer ---------- */}
        <div className="mt-5">
          <AdvancedSplitter
            key={splitterKey}
            ref={splitterRef}
            participants={splitParticipants}
            amount={splitAmount}
            currency={currency}
            payerName={payerName.trim()}
          />
        </div>

        <div className="mt-5 flex flex-col gap-3 sm:flex-row">
          <button
            type="submit"
            disabled={saving}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <>
                <Plus className="h-5 w-5" />
                Ausgabe hinzufügen
              </>
            )}
          </button>

          <button
            type="button"
            onClick={handleScanClick}
            disabled={saving}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-emerald-600 px-4 py-3 font-semibold text-emerald-700 transition hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Camera className="h-5 w-5" />
            Kassenbon scannen
          </button>
        </div>

        {/* Unsichtbarer Datei-Input: öffnet auf dem Handy direkt die Kamera */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={handleReceiptSelected}
        />

        {/* Hinweis während des Bon-Uploads (danach übernimmt ReceiptJobsPanel) */}
        {scanNotice && (
          <div className="mt-3 flex items-center justify-center gap-2 rounded-xl bg-emerald-50 px-4 py-3 text-center text-sm font-medium text-emerald-700">
            <Loader2 className="h-5 w-5 shrink-0 animate-spin" />
            {scanNotice}
          </div>
        )}

        {formError && (
          <p className="mt-3 text-center text-sm text-red-600">{formError}</p>
        )}
      </form>

      {/* Duplikats-Warnung als eigener Dialog (außerhalb des <form>) */}
      {duplicate && (
        <ConfirmDialog
          title="Mögliches Duplikat"
          message={duplicate.message}
          confirmLabel="Trotzdem speichern"
          loading={duplicateBusy}
          onConfirm={confirmDuplicate}
          onCancel={() => setDuplicate(null)}
        />
      )}
    </>
  );
}

export default ExpenseForm;
