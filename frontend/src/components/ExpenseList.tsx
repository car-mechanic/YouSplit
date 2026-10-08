import { useMemo, useState } from "react";
import { ArrowUpDown, Plus, Receipt } from "lucide-react";
import type { Expense } from "../api";
import { sortExpenses } from "../expenseSort";
import type { SortKey } from "../expenseSort";
import ExpenseListItem from "./ExpenseListItem";

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "date-desc", label: "Neueste zuerst" },
  { value: "date-asc", label: "Älteste zuerst" },
  { value: "amount-desc", label: "Teuerste zuerst" },
  { value: "amount-asc", label: "Günstigste zuerst" },
];

interface ExpenseListProps {
  expenses: Expense[];
  onEdit: (expense: Expense) => void;
  onDelete: (expense: Expense) => void;
  /** CTA im Empty State: springt zurück ins Ausgabenformular. */
  onAddFirst: () => void;
}

/**
 * Abschnitt "Bisherige Ausgaben": fixierter Kopf mit Sortier-Auswahl, darunter
 * die scrollbare Liste – oder ein freundlicher Empty State. Die Sortierung ist
 * hier gekapselt, weil sie nur die Anzeige betrifft (ListView muss davon nichts
 * wissen).
 */
function ExpenseList({
  expenses,
  onEdit,
  onDelete,
  onAddFirst,
}: ExpenseListProps) {
  const [sortKey, setSortKey] = useState<SortKey>("date-desc");

  const sortedExpenses = useMemo(
    () => sortExpenses(expenses, sortKey),
    [expenses, sortKey],
  );

  return (
    <section className="mt-6 overflow-hidden rounded-xl border border-gray-100 bg-white shadow-sm">
      {/* flex-wrap: auf schmalen Screens rutscht die Sortierung unter die
          Überschrift, statt sie umzubrechen und rechts überzustehen */}
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-gray-100 px-4 py-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold whitespace-nowrap text-gray-900">
          <Receipt className="h-5 w-5 text-emerald-600" />
          Bisherige Ausgaben
        </h2>

        {/* Sortier-Auswahl erst ab 2 Einträgen sinnvoll */}
        {expenses.length > 1 && (
          <label className="ml-auto flex items-center gap-1.5 text-sm text-gray-500">
            <ArrowUpDown className="h-4 w-4" />
            <span className="sr-only">Sortieren nach</span>
            <select
              value={sortKey}
              onChange={(event) => setSortKey(event.target.value as SortKey)}
              className="rounded-lg border border-gray-300 bg-white px-2 py-1.5 text-sm font-medium text-gray-700 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30"
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {expenses.length === 0 ? (
        <div className="flex flex-col items-center gap-4 px-6 py-12 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50">
            <Receipt className="h-7 w-7 text-emerald-600" />
          </div>
          <div>
            <p className="font-semibold text-gray-900">Noch keine Ausgaben</p>
            <p className="mt-1 text-sm text-gray-500">
              Trage die erste Ausgabe ein – der Kassensturz rechnet den
              Rest.
            </p>
          </div>
          <button
            type="button"
            onClick={onAddFirst}
            className="flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-5 py-3 font-semibold text-white transition hover:bg-emerald-700"
          >
            <Plus className="h-5 w-5" />
            Erste Ausgabe eintragen
          </button>
        </div>
      ) : (
        <ul className="max-h-[60vh] space-y-3 overflow-y-auto bg-gray-50 p-2 sm:p-4">
          {sortedExpenses.map((expense) => (
            <ExpenseListItem
              key={expense.id}
              expense={expense}
              onEdit={() => onEdit(expense)}
              onDelete={() => onDelete(expense)}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

export default ExpenseList;
