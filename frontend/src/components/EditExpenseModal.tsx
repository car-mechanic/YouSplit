import { useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Check, Loader2 } from "lucide-react";
import type { Expense, ExpenseUpdate } from "../api";
import { parseAmount } from "../format";
import { splitsFromRatio } from "../splitMath";
import AdvancedSplitter from "./AdvancedSplitter";
import CategorySelect from "./CategorySelect";
import type { AdvancedSplitterHandle } from "./AdvancedSplitter";
import CurrencySelect from "./CurrencySelect";
import DatePicker from "./DatePicker";
import Modal from "./Modal";

interface EditExpenseModalProps {
  expense: Expense;
  /** Bekannte Teilnehmer der Liste (für den Advanced Splitter). */
  participants: string[];
  /** Wählbare Kategorien der Liste (Standards + eigene). */
  categories: string[];
  saving: boolean;
  errorMessage: string | null;
  onSave: (data: ExpenseUpdate) => void;
  onCancel: () => void;
}

const inputClass =
  "w-full rounded-xl border border-gray-300 px-4 py-3 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30";
const labelClass = "mb-1 block text-sm font-medium text-gray-700";

function EditExpenseModal({
  expense,
  participants,
  categories,
  saving,
  errorMessage,
  onSave,
  onCancel,
}: EditExpenseModalProps) {
  const [title, setTitle] = useState(expense.title);
  // Betrag als String mit deutschem Dezimalkomma für die Eingabe
  const [amount, setAmount] = useState(
    expense.amount.toString().replace(".", ","),
  );
  const [payerName, setPayerName] = useState(expense.payer_name);
  const [currency, setCurrency] = useState(expense.currency);
  const splitterRef = useRef<AdvancedSplitterHandle>(null);
  const [category, setCategory] = useState(expense.category);
  // Ausgabendatum als ISO "YYYY-MM-DD". Alte, manuell erfasste Ausgaben haben
  // kein receipt_date → als Vorbelegung dient der Datumsanteil von created_at.
  const [date, setDate] = useState(
    (expense.receipt_date ?? expense.created_at).slice(0, 10),
  );
  const [localError, setLocalError] = useState<string | null>(null);

  // Stabile Teilnehmerbasis für die Startaufteilung: bekannte Personen der Liste
  // plus Original-Zahler und die in den gespeicherten splits genannten Namen.
  const baseParticipants = useMemo(() => {
    const names = [...participants];
    for (const name of [
      expense.payer_name,
      ...Object.keys(expense.splits ?? {}),
    ]) {
      if (name && !names.includes(name)) names.push(name);
    }
    return names;
  }, [participants, expense]);

  // Startaufteilung: gespeicherte splits – sonst treu aus split_ratio ableiten
  // (Altdaten/gescannte Bons behalten so ihre bisherige Aufteilung).
  const initialSplits = useMemo(
    () =>
      expense.splits && Object.keys(expense.splits).length > 0
        ? expense.splits
        : splitsFromRatio(
            baseParticipants,
            expense.payer_name,
            expense.amount,
            expense.split_ratio,
          ),
    [expense, baseParticipants],
  );

  // Live-Teilnehmer für den Splitter (inkl. eines evtl. umbenannten Zahlers).
  const splitParticipants = useMemo(() => {
    const names = [...baseParticipants];
    const current = payerName.trim();
    if (current && !names.includes(current)) names.push(current);
    return names;
  }, [baseParticipants, payerName]);

  // Betrag als Zahl fürs Splitter-Ergebnis (0, solange leer/ungültig).
  const parsedAmountValue = parseAmount(amount);
  const splitAmount = parsedAmountValue > 0 ? parsedAmountValue : 0;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();

    const parsedAmount = parseAmount(amount);
    if (!title.trim() || !payerName.trim()) {
      setLocalError("Bitte Titel und Zahler angeben.");
      return;
    }
    if (Number.isNaN(parsedAmount) || parsedAmount <= 0) {
      setLocalError("Bitte einen Betrag größer als 0 angeben.");
      return;
    }

    setLocalError(null);
    const split = splitterRef.current?.getResult();
    onSave({
      title: title.trim(),
      amount: parsedAmount,
      payer_name: payerName.trim(),
      split_ratio: split?.splitRatio ?? expense.split_ratio,
      category,
      receipt_date: date,
      currency,
      splits: split?.splits ?? null,
    });
  }

  return (
    <Modal title="Ausgabe bearbeiten" onClose={onCancel}>
      <form onSubmit={handleSubmit}>
        <div className="grid gap-4">
          <div>
            <label htmlFor="edit-title" className={labelClass}>
              Was wurde gekauft?
            </label>
            <input
              id="edit-title"
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={200}
              className={inputClass}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="edit-amount" className={labelClass}>
                Betrag
              </label>
              <div className="flex gap-2">
                <input
                  id="edit-amount"
                  type="text"
                  inputMode="decimal"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                  className={`${inputClass} flex-1`}
                />
                <CurrencySelect value={currency} onChange={setCurrency} />
              </div>
            </div>
            <div>
              <label htmlFor="edit-date" className={labelClass}>
                Datum
              </label>
              <DatePicker id="edit-date" value={date} onChange={setDate} />
            </div>
            <div>
              <label htmlFor="edit-payer" className={labelClass}>
                Wer hat bezahlt?
              </label>
              <input
                id="edit-payer"
                type="text"
                value={payerName}
                onChange={(event) => setPayerName(event.target.value)}
                maxLength={100}
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="edit-category" className={labelClass}>
                Kategorie
              </label>
              <CategorySelect
                id="edit-category"
                value={category}
                options={categories}
                onChange={setCategory}
              />
            </div>
          </div>

          <AdvancedSplitter
            ref={splitterRef}
            participants={splitParticipants}
            amount={splitAmount}
            currency={currency}
            payerName={payerName.trim()}
            initialSplits={initialSplits}
          />
        </div>

        {(localError || errorMessage) && (
          <p className="mt-3 text-sm text-red-600">
            {localError ?? errorMessage}
          </p>
        )}

        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onCancel}
            disabled={saving}
            className="rounded-xl border border-gray-300 px-4 py-3 font-semibold text-gray-700 transition hover:bg-gray-50 disabled:opacity-50"
          >
            Abbrechen
          </button>
          <button
            type="submit"
            disabled={saving}
            className="flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <>
                <Check className="h-5 w-5" />
                Speichern
              </>
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
}

export default EditExpenseModal;
