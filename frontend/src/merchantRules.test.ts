import { describe, expect, it } from "vitest";
import type { BankTransaction } from "./api";
import {
  applyClassifications,
  foldKeyword,
  isKeywordValid,
  suggestKeyword,
} from "./merchantRules";

function row(overrides: Partial<BankTransaction>): BankTransaction {
  return {
    index: 0,
    booking_date: "2026-03-12",
    description: "",
    amount: -10,
    category: null,
    label: null,
    is_food: false,
    duplicate: false,
    sign_guessed: false,
    ...overrides,
  };
}

describe("foldKeyword", () => {
  it("folds like the backend: case, umlauts, accents and punctuation", () => {
    expect(foldKeyword("Hans Meier e.K.")).toBe("HANS MEIER E K");
    expect(foldKeyword("Bäckerei Müller-Groß")).toBe("BAECKEREI MUELLER GROSS");
    expect(foldKeyword("Café  Crème")).toBe("CAFE CREME");
    expect(foldKeyword("  *** ")).toBe("");
  });
});

describe("isKeywordValid", () => {
  it("counts only letters and digits", () => {
    expect(isKeywordValid("Edk")).toBe(true);
    expect(isKeywordValid("ab")).toBe(false);
    expect(isKeywordValid("e.K.")).toBe(false);
    expect(isKeywordValid("  - ")).toBe(false);
  });
});

describe("suggestKeyword", () => {
  it("strips booking prefixes, numbers and the place after the legal form", () => {
    expect(
      suggestKeyword(
        "Kartenzahlung Hans Meier e.K. Musterstadt 12.03. Karte 1234",
        null,
      ),
    ).toBe("Hans Meier e.K.");
  });

  it("skips PayPal markers and stops at filler words", () => {
    expect(suggestKeyword("PayPal *Bauernhof Schulz sagt Danke", null)).toBe(
      "Bauernhof Schulz",
    );
  });

  it("skips leading dates and stops at a number", () => {
    expect(
      suggestKeyword("Basis-Lastschrift 12.03.2026 Hofladen Lindner 4711 Ref", null),
    ).toBe("Hofladen Lindner");
  });

  it("ends at a comma and after four words", () => {
    expect(suggestKeyword("Lastschrift Bio Markt Krause, Leipzig", null)).toBe(
      "Bio Markt Krause",
    );
    expect(suggestKeyword("Eins Zwei Drei Vier Fünf", null)).toBe(
      "Eins Zwei Drei Vier",
    );
  });

  it("prefers the recognized label if it occurs in the text", () => {
    expect(suggestKeyword("Kartenzahlung REWE Markt GmbH 1234", "Rewe")).toBe(
      "Rewe",
    );
    // A display name of a franchise operator is not in the text: take the text.
    expect(
      suggestKeyword("Lastschrift Yazici Einzelhandels OHG", "Rewe"),
    ).toBe("Yazici Einzelhandels OHG");
  });

  it("returns an empty suggestion when nothing usable is left", () => {
    expect(suggestKeyword("Kartenzahlung 12,34 EUR 4711", null)).toBe("");
  });
});

describe("applyClassifications", () => {
  it("updates rows and selection only where the food status changed", () => {
    const owner = row({ index: 0, description: "Hans Meier e.K." });
    const rewe = row({
      index: 1,
      description: "REWE",
      category: "Lebensmittel",
      label: "Rewe",
      is_food: true,
    });
    const dup = row({ index: 2, description: "Hans Meier e.K.", duplicate: true });
    const income = row({ index: 3, description: "Gehalt", amount: 2000 });
    const all = [owner, rewe, dup, income];
    const expenses = [owner, rewe, dup];

    const result = applyClassifications(
      all,
      expenses,
      [
        { category: "Lebensmittel", label: "Hans Meier E K", is_food: true },
        { category: "Ignorieren", label: "Rewe", is_food: false },
        { category: "Lebensmittel", label: "Hans Meier E K", is_food: true },
      ],
      new Set([1, 7]),
    );

    expect(result.transactions.map((t) => t.is_food)).toEqual([
      true,
      false,
      true,
      false,
    ]);
    expect(result.transactions[1].category).toBe("Ignorieren");
    expect(result.transactions[3]).toBe(income);
    // New food preselected, the duplicate not, the ignored row deselected,
    // unrelated selections kept.
    expect([...result.selected].sort()).toEqual([0, 7]);
  });
});
