import type { BankClassification, BankTransaction } from "./api";

/**
 * Helpers for remembered merchants in the bank statement import. Matching
 * itself happens in the backend (`bank_statement.classify`); the frontend only
 * suggests a keyword and merges the backend's new classification.
 */

/** Same minimum as `category_rules.MIN_KEYWORD_LENGTH` in the backend. */
export const MIN_KEYWORD_LENGTH = 3;

/** Longest suggestion; owner names rarely need more. */
const MAX_SUGGESTION_LENGTH = 60;
/** More words are usually city or street, not the merchant. */
const MAX_SUGGESTION_WORDS = 4;

const FOLD_MAP: Record<string, string> = { Ä: "AE", Ö: "OE", Ü: "UE", ß: "SS" };

/**
 * Mirror of `_fold` in `bank_statement.py`: upper case, umlauts spelled out,
 * accents removed, every run of other characters becomes one space. Rules match
 * on this form, so the frontend checks length and occurrence the same way.
 */
export function foldKeyword(text: string): string {
  return text
    .toUpperCase()
    .replace(/[ÄÖÜß]/g, (ch) => FOLD_MAP[ch] ?? ch)
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .replace(/[^A-Z0-9]+/g, " ")
    .trim();
}

/** Long enough for the backend (letters and digits only, like the backend). */
export function isKeywordValid(keyword: string): boolean {
  return foldKeyword(keyword).replace(/ /g, "").length >= MIN_KEYWORD_LENGTH;
}

// Booking prefixes and filler words that are not part of a merchant name
// (folded form). Kept close to `_LABEL_NOISE` in the backend.
const NOISE_WORDS = new Set([
  "KARTENZAHLUNG", "LASTSCHRIFT", "BASISLASTSCHRIFT", "FOLGELASTSCHRIFT",
  "ERSTLASTSCHRIFT", "UEBERWEISUNG", "DAUERAUFTRAG", "SEPA", "PAYPAL",
  "BASIS LASTSCHRIFT", "GIROCARD", "DEBITK", "DEBITKARTE", "DEBIT", "VISA", "MASTERCARD", "MAESTRO",
  "EC", "KARTE", "ZAHLUNG", "KAUF", "EINKAUF", "UMSATZ", "POS", "ELV", "OLV",
  "APPLE", "GOOGLE", "PAY", "KONTAKTLOS", "NR", "VOM", "UHR", "EUR",
  "GUTSCHRIFT", "SAGT", "DANKE", "IHR", "BEI", "REF", "MANDAT", "MREF", "CRED",
]);

// Legal forms end a merchant name ("Hans Meier e.K. Musterstadt"); they stay in
// the keyword because they make it more specific.
const LEGAL_FORMS = new Set(["EK", "EKFM", "EKFR", "OHG", "KG", "GMBH", "UG", "AG", "GBR"]);

/**
 * Keyword suggestion for "Händler merken".
 *
 * The recognized merchant name wins if it really occurs in the booking text
 * (a display name like "Rewe" for a franchise operator does not, and a rule
 * with it would never match). Otherwise the merchant is taken from the text:
 * booking prefixes (Kartenzahlung, PayPal …), dates and numbers are skipped,
 * then up to four words are taken until a number, filler word, comma or
 * legal form.
 */
export function suggestKeyword(description: string, label: string | null): string {
  if (label && isKeywordValid(label)) {
    const folded = ` ${foldKeyword(description)} `;
    if (folded.includes(` ${foldKeyword(label)} `)) return label;
  }

  const words: string[] = [];
  for (const raw of description.split(/\s+/)) {
    // "*LIDL" (PayPal) and quotes around names are noise, inner dots ("e.K.") not.
    const token = raw.replace(/^[^\p{L}\p{N}]+/u, "").replace(/[,;:/|]+$/, "");
    const folded = foldKeyword(token);
    const compact = folded.replace(/ /g, "");
    const isNoise = !folded || NOISE_WORDS.has(folded) || /\d/.test(token);

    if (words.length === 0) {
      if (isNoise) continue;
    } else if (isNoise) {
      break;
    }
    words.push(token);
    if (
      LEGAL_FORMS.has(compact) ||
      /[,;:/|]$/.test(raw) ||
      words.length === MAX_SUGGESTION_WORDS
    ) {
      break;
    }
  }

  const suggestion = words.join(" ").slice(0, MAX_SUGGESTION_LENGTH).trim();
  return isKeywordValid(suggestion) ? suggestion : "";
}

/**
 * Merge the backend's new classification into the preview.
 *
 * `results` belong to `expenseRows` in the same order (only expenses are sent).
 * Selection follows only rows whose food status changed: newly recognized food
 * is preselected (unless it already exists in the list), rows that are no
 * longer food are deselected. Everything the user picked by hand stays.
 */
export function applyClassifications(
  transactions: BankTransaction[],
  expenseRows: BankTransaction[],
  results: BankClassification[],
  selected: ReadonlySet<number>,
): { transactions: BankTransaction[]; selected: Set<number> } {
  const byIndex = new Map<number, BankClassification>();
  expenseRows.forEach((row, position) => {
    const result = results[position];
    if (result) byIndex.set(row.index, result);
  });

  const nextSelected = new Set(selected);
  const next = transactions.map((transaction) => {
    const result = byIndex.get(transaction.index);
    if (!result) return transaction;
    const isFood = result.is_food && transaction.amount < 0;
    if (isFood !== transaction.is_food) {
      if (isFood && !transaction.duplicate) nextSelected.add(transaction.index);
      if (!isFood) nextSelected.delete(transaction.index);
    }
    return {
      ...transaction,
      category: result.category,
      label: result.label,
      is_food: isFood,
    };
  });
  return { transactions: next, selected: nextSelected };
}
