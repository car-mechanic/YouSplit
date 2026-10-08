import type { Expense } from "./api";
import { shownDate } from "./expenseSort";

/**
 * Zeitraum der Statistik. Tage als ISO "YYYY-MM-DD", Monat als "YYYY-MM"; die
 * Grenzen eines eigenen Zeitraums zählen mit (15. bis 25. = beide Tage dabei).
 */
export type StatsRange =
  | { kind: "all" }
  | { kind: "month"; month: string }
  | { kind: "custom"; from: string; to: string };

/** Monate mit Ausgaben, neueste zuerst – die Schnellauswahl im Dropdown. */
export function availableMonths(expenses: readonly Expense[]): string[] {
  const months = new Set(
    expenses.map((expense) => shownDate(expense).slice(0, 7)),
  );
  return [...months].sort().reverse();
}

/** "2026-06" → "Juni 2026". */
export function monthLabel(month: string): string {
  const [year, monthIndex] = month.split("-").map(Number);
  return new Intl.DateTimeFormat("de-DE", {
    month: "long",
    year: "numeric",
  }).format(new Date(year, monthIndex - 1, 1));
}

/** Liegt der Tag im Zeitraum? Ein verdrehter eigener Zeitraum zählt richtig herum. */
export function isInRange(day: string, range: StatsRange): boolean {
  switch (range.kind) {
    case "all":
      return true;
    case "month":
      return day.slice(0, 7) === range.month;
    case "custom": {
      const [from, to] =
        range.from <= range.to
          ? [range.from, range.to]
          : [range.to, range.from];
      return from <= day && day <= to;
    }
  }
}

/** Ausgaben im Zeitraum; maßgeblich ist der angezeigte Tag der Ausgabe. */
export function filterByRange(
  expenses: readonly Expense[],
  range: StatsRange,
): Expense[] {
  return expenses.filter((expense) => isInRange(shownDate(expense), range));
}
