import type { Expense } from "./api";

/**
 * Standard-Kategorien im Dropdown. Spiegel von `categories.DEFAULT_CATEGORIES`
 * im Backend (die Bon-KI wählt aus genau dieser Liste). "Sonstiges" ist der
 * Auffang-Wert, wenn nichts passt.
 */
export const DEFAULT_CATEGORIES = [
  "Lebensmittel",
  "Auswärtsessen",
  "Haushalt",
  "Drogerie",
  "Freizeit",
  "Mobilität",
  "Sonstiges",
] as const;

export const FALLBACK_CATEGORY = "Sonstiges";

/** Altwert ohne Kategorie (frühere manuelle Einträge, gescheiterte Scans). */
export const UNCATEGORIZED = "Unknown/Manuell";

/** Anzeigename einer Kategorie: der technische Altwert liest sich schlecht. */
export function categoryLabel(category: string): string {
  return !category.trim() || category === UNCATEGORIZED
    ? "Ohne Kategorie"
    : category;
}

/**
 * Alle wählbaren Kategorien einer Liste: die Standards, dahinter jede eigene
 * Kategorie, die in der Liste schon vorkommt (alphabetisch). Eigene Kategorien
 * werden so mit der Ausgabe gespeichert und stehen danach allen Personen der
 * Liste zur Auswahl, ohne eigene Tabelle.
 */
export function categoryOptions(expenses: readonly Expense[]): string[] {
  const defaults: readonly string[] = DEFAULT_CATEGORIES;
  const custom = new Set<string>();
  for (const expense of expenses) {
    const category = expense.category.trim();
    if (
      category &&
      category !== UNCATEGORIZED &&
      !defaults.includes(category)
    ) {
      custom.add(category);
    }
  }
  return [...defaults, ...[...custom].sort((a, b) => a.localeCompare(b, "de"))];
}

// Stichwörter je Standard-Kategorie. Ein Stichwort trifft ein ganzes Wort des
// Titels; ab 4 Zeichen auch als Wortteil ("pizz" trifft "Pizzeria").
const KEYWORDS: Record<string, readonly string[]> = {
  Lebensmittel: [
    "rewe",
    "edeka",
    "aldi",
    "lidl",
    "netto",
    "penny",
    "kaufland",
    "real",
    "norma",
    "tegut",
    "globus",
    "spar",
    "supermarkt",
    "einkauf",
    "wocheneinkauf",
    "lebensmittel",
    "bäcker",
    "bäckerei",
    "brötchen",
    "metzger",
    "getränke",
    "obst",
    "gemüse",
  ],
  Auswärtsessen: [
    "restaurant",
    "pizz",
    "döner",
    "burger",
    "sushi",
    "imbiss",
    "kebab",
    "café",
    "cafe",
    "kaffee",
    "mittagessen",
    "abendessen",
    "frühstück",
    "essen",
    "lieferando",
    "wolt",
    "mcdonald",
    "bar",
    "kneipe",
    "eis",
    "biergarten",
  ],
  Haushalt: [
    "ikea",
    "obi",
    "hornbach",
    "bauhaus",
    "baumarkt",
    "putzmittel",
    "möbel",
    "haushalt",
    "strom",
    "internet",
    "miete",
    "reparatur",
  ],
  Drogerie: ["dm", "rossmann", "müller", "drogerie", "apotheke", "kosmetik"],
  Freizeit: [
    "kino",
    "konzert",
    "museum",
    "eintritt",
    "ticket",
    "bowling",
    "schwimmbad",
    "netflix",
    "spotify",
    "urlaub",
    "hotel",
    "airbnb",
    "ausflug",
    "geschenk",
  ],
  Mobilität: [
    "tanken",
    "tankstelle",
    "benzin",
    "diesel",
    "aral",
    "shell",
    "esso",
    "bahn",
    "zug",
    "bus",
    "taxi",
    "uber",
    "parken",
    "parkhaus",
    "maut",
    "flug",
    "mietwagen",
    "sprit",
  ],
};

const normalize = (text: string) => text.trim().toLocaleLowerCase("de");
const words = (text: string) =>
  normalize(text)
    .split(/[^\p{L}\p{N}]+/u)
    .filter(Boolean);

/**
 * Kategorie-Vorschlag zum Titel einer neuen Ausgabe – oder `null`.
 *
 * 1. Gelernt: Gab es in der Liste schon eine Ausgabe mit gleichem Titel, gilt
 *    deren Kategorie (die jüngste zählt). So übernimmt "Pizza Luigi" beim
 *    zweiten Mal, was die Gruppe beim ersten Mal gewählt hat – auch eigene
 *    Kategorien.
 * 2. Stichwörter: "REWE", "Pizzeria", "Tanken" … ergeben eine Standard-Kategorie.
 */
export function suggestCategory(
  title: string,
  expenses: readonly Expense[],
): string | null {
  const key = normalize(title);
  if (!key) return null;

  const learned = expenses
    .filter(
      (expense) =>
        normalize(expense.title) === key &&
        expense.category.trim() &&
        expense.category !== UNCATEGORIZED,
    )
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  if (learned) return learned.category;

  // Das längste treffende Stichwort gewinnt: "Baumarkt" ist Haushalt, obwohl
  // auch "markt" (Lebensmittel) darin steckt.
  const titleWords = words(title);
  let best: { category: string; length: number } | null = null;
  for (const [category, keywords] of Object.entries(KEYWORDS)) {
    for (const keyword of keywords) {
      const hit = titleWords.some(
        (word) =>
          word === keyword || (keyword.length >= 4 && word.includes(keyword)),
      );
      if (hit && (best === null || keyword.length > best.length)) {
        best = { category, length: keyword.length };
      }
    }
  }
  return best?.category ?? null;
}
