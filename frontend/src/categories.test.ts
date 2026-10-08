import { describe, expect, it } from "vitest";
import {
  categoryLabel,
  categoryOptions,
  DEFAULT_CATEGORIES,
  suggestCategory,
} from "./categories";
import { makeExpense } from "./testExpense";

describe("categoryOptions", () => {
  it("zeigt ohne Ausgaben die Standard-Kategorien", () => {
    expect(categoryOptions([])).toEqual([...DEFAULT_CATEGORIES]);
  });

  it("hängt eigene Kategorien der Liste alphabetisch an, ohne Doppelte und Altwert", () => {
    const expenses = [
      makeExpense({ category: "Urlaubskasse" }),
      makeExpense({ category: "Geschenke" }),
      makeExpense({ category: "Urlaubskasse" }),
      makeExpense({ category: "Lebensmittel" }),
      makeExpense({ category: "Unknown/Manuell" }),
    ];
    expect(categoryOptions(expenses)).toEqual([
      ...DEFAULT_CATEGORIES,
      "Geschenke",
      "Urlaubskasse",
    ]);
  });
});

describe("categoryLabel", () => {
  it("benennt den Altwert lesbar und lässt alles andere stehen", () => {
    expect(categoryLabel("Unknown/Manuell")).toBe("Ohne Kategorie");
    expect(categoryLabel("")).toBe("Ohne Kategorie");
    expect(categoryLabel("Freizeit")).toBe("Freizeit");
  });
});

describe("suggestCategory", () => {
  it.each([
    ["REWE", "Lebensmittel"],
    ["Wocheneinkauf Edeka", "Lebensmittel"],
    ["Pizzeria Da Mario", "Auswärtsessen"],
    ["Döner", "Auswärtsessen"],
    ["Tanken Aral", "Mobilität"],
    ["Bahn nach Hamburg", "Mobilität"],
    ["dm", "Drogerie"],
    ["Kino", "Freizeit"],
    ["IKEA Regal", "Haushalt"],
    ["Baumarkt", "Haushalt"],
    ["Eiscafé Venezia", "Auswärtsessen"],
  ])("schlägt für %j %j vor", (title, expected) => {
    expect(suggestCategory(title, [])).toBe(expected);
  });

  it("trifft kurze Stichwörter nur als ganzes Wort", () => {
    // "dm" steckt in "Admiral", "bar" in "Barbara" – beides kein Treffer
    expect(suggestCategory("Admiral", [])).toBeNull();
    expect(suggestCategory("Geschenk für Barbara", [])).toBe("Freizeit");
    expect(suggestCategory("Barbara", [])).toBeNull();
  });

  it("liefert ohne Treffer oder leeren Titel null", () => {
    expect(suggestCategory("", [])).toBeNull();
    expect(suggestCategory("Xyz", [])).toBeNull();
  });

  it("lernt aus der Liste: gleicher Titel bekommt die zuletzt gewählte Kategorie", () => {
    const expenses = [
      makeExpense({
        title: "Pizza Luigi",
        category: "Freizeit",
        created_at: "2026-08-01T10:00:00Z",
      }),
      makeExpense({
        title: "pizza luigi ",
        category: "Wochenende",
        created_at: "2026-08-05T10:00:00Z",
      }),
    ];
    expect(suggestCategory("Pizza Luigi", expenses)).toBe("Wochenende");
  });

  it("lernt nichts aus Einträgen ohne Kategorie", () => {
    const expenses = [
      makeExpense({ title: "REWE", category: "Unknown/Manuell" }),
    ];
    expect(suggestCategory("REWE", expenses)).toBe("Lebensmittel");
  });
});
