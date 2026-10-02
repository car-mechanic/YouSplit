export const formatEuro = (value: number): string =>
  new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(
    value,
  );

/**
 * Formatiert einen Betrag in seiner Erfassungswährung (Multi-Currency).
 * EUR wird mit dem €-Symbol gezeigt ("24,50 €"), Fremdwährungen mit ihrem
 * ISO-Code ("50,00 USD") — so ist auf einen Blick klar, dass es NICHT Euro ist.
 */
export const formatMoney = (value: number, currency: string): string =>
  new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency,
    currencyDisplay: currency === "EUR" ? "symbol" : "code",
  }).format(value);

/**
 * Formatiert ein ISO-Datum (nur der Datumsanteil "YYYY-MM-DD" wird genutzt,
 * auch aus einem vollen Zeitstempel) als deutsches Datum "TT.MM.JJJJ".
 * Die Komponenten werden LOKAL interpretiert (`new Date(y, m-1, d)`), damit
 * Zeitzonen den Kalendertag nicht um einen Tag verschieben.
 */
export const formatDate = (iso: string): string => {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  if (!year || !month || !day) return "";
  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(year, month - 1, day));
};
