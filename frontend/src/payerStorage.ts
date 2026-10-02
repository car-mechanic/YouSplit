/**
 * Geräte-Erkennung: pro Liste den zuletzt genutzten Zahler-Namen im
 * localStorage merken. Geteilt von ExpenseForm und BankStatementView, damit
 * beide denselben Namen vorschlagen.
 */
export const payerStorageKey = (listId: string): string =>
  `yousplit:list:${listId}:payer`;
