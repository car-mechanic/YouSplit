/**
 * Geräte-Erkennung: pro Liste den zuletzt genutzten Zahler-Namen im
 * localStorage merken. Geteilt von ExpenseForm und BankStatementView, damit
 * beide denselben Namen vorschlagen.
 */
export const payerStorageKey = (listId: string): string =>
  `yousplit:list:${listId}:payer`;

/**
 * Vorgeschlagener Zahler: der auf diesem Gerät gemerkte Name, sonst die mit
 * dem Home-Assistant-Benutzer verknüpfte Person (gilt auf jedem Gerät).
 */
export function initialPayer(listId: string, linkedName: string | null): string {
  let stored: string | undefined;
  try {
    stored = localStorage.getItem(payerStorageKey(listId))?.trim();
  } catch {
    // Speicher nicht verfügbar (privater Modus): nur kein Gerätename
  }
  return stored || linkedName || "";
}
