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
 * Liest einen getippten Betrag: "24,50", "24.50", "1.234,56", "12 €".
 * Kommen Punkt UND Komma vor, ist das letzte der beiden das Dezimalzeichen, das
 * andere gliedert Tausender. Liefert NaN, wenn die Eingabe kein Betrag ist.
 *
 * Ersetzt `Number.parseFloat(text.replace(",", "."))`: das las "1.234,56" still
 * als 1,234 und "12abc" als 12.
 */
export function parseAmount(input: string): number {
  let text = input.replace(/[\s€]/g, "");
  if (!/^[\d.,]+$/.test(text)) return Number.NaN;

  const lastComma = text.lastIndexOf(",");
  const lastDot = text.lastIndexOf(".");
  if (lastComma >= 0 && lastDot >= 0) {
    const thousands = lastComma > lastDot ? "." : ",";
    text = text.split(thousands).join("");
  } else if (text.split(".").length > 2) {
    // Mehrere Punkte ohne Komma sind Tausenderpunkte ("1.234.567")
    text = text.split(".").join("");
  }

  // Number() statt parseFloat: lehnt Reste wie ein zweites Komma ab (→ NaN)
  return /\d/.test(text) ? Number(text.replace(",", ".")) : Number.NaN;
}

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
