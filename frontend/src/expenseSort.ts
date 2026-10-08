import type { Expense } from "./api";

export type SortKey = "date-desc" | "date-asc" | "amount-desc" | "amount-asc";

/**
 * Der Tag, den die Card anzeigt: das Ausgaben-/Bon-Datum, bei Altdaten ohne
 * `receipt_date` der Anlagetag. ISO "YYYY-MM-DD" sortiert lexikografisch =
 * chronologisch.
 */
export const shownDate = (expense: Expense): string =>
  expense.receipt_date ?? expense.created_at.slice(0, 10);

/** EUR-Wert: nur so sind Beträge verschiedener Währungen vergleichbar. */
const eurValue = (expense: Expense): number =>
  expense.amount * expense.exchange_rate;

function compareByDate(a: Expense, b: Expense): number {
  // Gleicher Tag (z. B. importierter Kontoauszug): Reihenfolge des Anlegens
  return (
    shownDate(a).localeCompare(shownDate(b)) ||
    a.created_at.localeCompare(b.created_at)
  );
}

/**
 * Sortierte Kopie der Ausgaben (die Eingabe bleibt unverändert). Nach Datum zählt
 * der ANGEZEIGTE Tag, nicht der Anlagezeitpunkt: eine heute nachgetragene Ausgabe
 * von letzter Woche steht sonst fälschlich ganz oben.
 */
export function sortExpenses(
  expenses: readonly Expense[],
  sortKey: SortKey,
): Expense[] {
  const items = [...expenses];
  switch (sortKey) {
    case "date-asc":
      return items.sort(compareByDate);
    case "amount-desc":
      return items.sort((a, b) => eurValue(b) - eurValue(a));
    case "amount-asc":
      return items.sort((a, b) => eurValue(a) - eurValue(b));
    case "date-desc":
      return items.sort((a, b) => compareByDate(b, a));
  }
}
