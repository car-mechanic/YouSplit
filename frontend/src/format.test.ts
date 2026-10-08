import { describe, expect, it } from "vitest";
import { formatDate, formatMoney, parseAmount } from "./format";

describe("parseAmount", () => {
  it.each([
    ["24,50", 24.5],
    ["24.50", 24.5],
    ["24", 24],
    [" 12 € ", 12],
    ["1.234,56", 1234.56],
    ["1,234.56", 1234.56],
    ["1.234.567", 1234567],
    ["1.234.567,89", 1234567.89],
    [",5", 0.5],
    ["5,", 5],
    ["0", 0],
  ])("liest %j als %d", (input, expected) => {
    expect(parseAmount(input)).toBeCloseTo(expected, 10);
  });

  it.each(["", "   ", "abc", "12abc", "1,2,3", "-5", ".", ",", "1e5"])(
    "lehnt %j ab",
    (input) => {
      expect(parseAmount(input)).toBeNaN();
    },
  );

  it("liest 1.234,56 nicht mehr als 1,234 (früher parseFloat)", () => {
    expect(parseAmount("1.234,56")).not.toBeCloseTo(1.234, 3);
  });
});

describe("formatMoney", () => {
  it("zeigt EUR mit Symbol und Fremdwährungen mit ISO-Code", () => {
    // Intl trennt Zahl und Währung mit einem geschützten Leerzeichen
    expect(formatMoney(24.5, "EUR").replace(/\s/g, " ")).toBe("24,50 €");
    expect(formatMoney(50, "USD").replace(/\s/g, " ")).toBe("50,00 USD");
  });
});

describe("formatDate", () => {
  it("nimmt den Kalendertag ohne Zeitzonen-Verschiebung", () => {
    expect(formatDate("2026-08-12")).toBe("12.08.2026");
    expect(formatDate("2026-08-12T23:30:00+00:00")).toBe("12.08.2026");
  });

  it("gibt bei unlesbarem Wert einen leeren Text zurück", () => {
    expect(formatDate("")).toBe("");
  });
});
