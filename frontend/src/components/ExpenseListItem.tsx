import { Calendar, Pencil, Tag, Trash2, User } from "lucide-react";
import type { Expense } from "../api";
import { categoryLabel } from "../categories";
import { formatDate, formatEuro, formatMoney } from "../format";

interface ExpenseListItemProps {
  expense: Expense;
  onEdit: () => void;
  onDelete: () => void;
}

/**
 * Eine einzelne Ausgabe als Card: Titel, Meta-Zeile (Zahler, Datum, Kategorie),
 * Betrag samt Eigenanteil und die Aktionen Bearbeiten/Löschen. Rein darstellend –
 * die eigentlichen Aktionen liegen beim Aufrufer.
 */
function ExpenseListItem({ expense, onEdit, onDelete }: ExpenseListItemProps) {
  // Anzahl Personen mit einem Anteil > 0 (nur bei expliziter Advanced-Split-
  // Aufteilung); dient der dezenten Zusatzinfo "· auf N aufgeteilt".
  const shareCount = expense.splits
    ? Object.values(expense.splits).filter((value) => value > 0).length
    : 0;

  return (
    <li className="flex items-center gap-2 rounded-xl border border-gray-100 bg-white p-3 shadow-sm transition hover:border-emerald-200 sm:gap-3 sm:p-4">
      <div className="min-w-0 flex-1">
        <p className="truncate font-semibold text-gray-900">{expense.title}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-gray-500">
          <span className="flex items-center gap-1">
            <User className="h-3.5 w-3.5" />
            {expense.payer_name}
          </span>
          <span className="flex items-center gap-1">
            <Calendar className="h-3.5 w-3.5" />
            {/* Bevorzugt das Bon-Datum; ältere Einträge ohne receipt_date
                fallen auf den Anlagezeitpunkt zurück. */}
            {formatDate(expense.receipt_date ?? expense.created_at)}
          </span>
          <span className="flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs">
            <Tag className="h-3 w-3" />
            {categoryLabel(expense.category)}
          </span>
        </div>
      </div>

      <div className="shrink-0 text-right">
        {/* Originalbetrag in Erfassungswährung; bei Fremdwährung darunter dezent
            der umgerechnete EUR-Betrag (Basis für Kassensturz & Statistiken) */}
        <p className="font-bold text-gray-900">
          {formatMoney(expense.amount, expense.currency)}
        </p>
        {expense.currency !== "EUR" && (
          <p className="text-xs text-gray-500">
            ≈ {formatEuro(expense.amount * expense.exchange_rate)}
          </p>
        )}
        {/* Eigenanteil des Zahlers (split_ratio als Prozent); bei expliziter
            Aufteilung zusätzlich die Anzahl beteiligter Personen. */}
        <p className="text-xs text-gray-400">
          trägt {Math.round(expense.split_ratio * 100)} %
          {/* Schmale Screens: eigene Zeile, sonst drückt der lange Text die
              Meta-Zeile links zusammen und überlappt das Datum. */}
          {shareCount > 1 && (
            <>
              <span className="hidden sm:inline"> · </span>
              <span className="block sm:inline">
                auf {shareCount} aufgeteilt
              </span>
            </>
          )}
        </p>
      </div>

      <div className="flex shrink-0 flex-col items-center gap-1 sm:flex-row">
        <button
          type="button"
          onClick={onEdit}
          aria-label="Bearbeiten"
          className="rounded-lg p-2 text-gray-400 transition hover:bg-emerald-50 hover:text-emerald-700"
        >
          <Pencil className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={onDelete}
          aria-label="Löschen"
          className="rounded-lg p-2 text-gray-400 transition hover:bg-red-50 hover:text-red-600"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </li>
  );
}

export default ExpenseListItem;
