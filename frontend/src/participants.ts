import type { Expense } from "./api";

/**
 * Alle Personen einer Liste in Reihenfolge ihres ersten Auftretens: zuerst die
 * festen Personen der Liste (`members`, aus dem Tutorial), dann Zahler und
 * alle, denen eine Aufteilung (`splits`) einen Anteil zuweist. Spiegel von
 * `settlement.collect_persons` im Backend: Formular, Bearbeiten-Dialog und
 * Kontoauszug-Import kennen so dieselben Personen wie der Kassensturz.
 */
export function collectParticipants(
  expenses: readonly Expense[],
  members: readonly string[] = [],
): string[] {
  const names: string[] = [];
  const seen = new Set<string>();
  const add = (name: string) => {
    if (seen.has(name)) return;
    seen.add(name);
    names.push(name);
  };
  members.forEach(add);
  for (const expense of expenses) {
    add(expense.payer_name);
    for (const name of Object.keys(expense.splits ?? {})) add(name);
  }
  return names;
}
