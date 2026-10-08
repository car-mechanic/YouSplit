import type { Expense } from "./api";

/** Test-Helfer: eine vollständige Ausgabe, einzelne Felder überschreibbar. */
export function makeExpense(overrides: Partial<Expense> = {}): Expense {
  return {
    id: "id",
    list_id: "list",
    title: "Pizza",
    amount: 10,
    payer_name: "Kev",
    split_ratio: 0.5,
    category: "Restaurant",
    created_at: "2026-08-12T10:00:00+00:00",
    receipt_date: null,
    currency: "EUR",
    exchange_rate: 1,
    splits: null,
    ...overrides,
  };
}
