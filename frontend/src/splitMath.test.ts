import { describe, expect, it } from "vitest";
import {
  clampValue,
  convertMode,
  deriveSplitRatio,
  distributeEvenly,
  fairEntries,
  redistributeUnlocked,
  resolveAmounts,
  resolveSplits,
  splitsFromRatio,
  syncEntries,
} from "./splitMath";
import type { SplitEntry } from "./splitMath";

const cents = (values: number[]) =>
  values.reduce((sum, value) => sum + Math.round(value * 100), 0);

const entry = (name: string, value: number, locked = false): SplitEntry => ({
  name,
  value,
  locked,
});

describe("distributeEvenly", () => {
  it("gibt den Rest-Cent der gewählten Position", () => {
    expect(distributeEvenly(100, 3)).toEqual([33.34, 33.33, 33.33]);
    expect(distributeEvenly(100, 3, 2)).toEqual([33.33, 33.33, 33.34]);
    expect(distributeEvenly(10, 4)).toEqual([2.5, 2.5, 2.5, 2.5]);
  });

  it("liefert ohne Positionen nichts", () => {
    expect(distributeEvenly(10, 0)).toEqual([]);
  });
});

describe("resolveAmounts", () => {
  it("trifft die Summe immer auf den Cent genau", () => {
    for (const amount of [0.01, 0.1, 1, 9.99, 10, 33.33, 100, 1234.57]) {
      for (const count of [1, 2, 3, 6, 7]) {
        const entries = fairEntries(
          Array.from({ length: count }, (_, i) => `P${i}`),
          "percent",
          amount,
        );
        const amounts = resolveAmounts(entries, amount);
        expect(cents(amounts), `${amount} auf ${count}`).toBe(Math.round(amount * 100));
        expect(Math.min(...amounts)).toBeGreaterThanOrEqual(0);
      }
    }
  });

  it("gibt den Rest-Cent der ersten ungelockten Person", () => {
    const entries = [entry("A", 33.33, true), entry("B", 33.34), entry("C", 33.33)];
    expect(resolveAmounts(entries, 10)).toEqual([3.33, 3.34, 3.33]);
  });

  it("bleibt bei Locks über 100 % ohne negative Anteile und summengenau", () => {
    const entries = [entry("A", 80, true), entry("B", 80, true), entry("C", 0)];
    const amounts = resolveAmounts(entries, 10);
    expect(cents(amounts)).toBe(1000);
    expect(Math.min(...amounts)).toBeGreaterThanOrEqual(0);
  });

  it("teilt gleichmäßig, wenn alle Gewichte 0 sind", () => {
    expect(resolveAmounts([entry("A", 0), entry("B", 0)], 10)).toEqual([5, 5]);
  });
});

describe("redistributeUnlocked", () => {
  it("verteilt den Rest nach einem Lock gleichmäßig auf die anderen", () => {
    const entries = [entry("A", 50, true), entry("B", 0), entry("C", 0)];
    expect(redistributeUnlocked(entries, "percent", 90).map((e) => e.value)).toEqual([
      50, 25, 25,
    ]);
    const amounts = [entry("A", 30, true), entry("B", 0), entry("C", 0)];
    expect(redistributeUnlocked(amounts, "amount", 90).map((e) => e.value)).toEqual([
      30, 30, 30,
    ]);
  });

  it("hält das Verhältnis einer eigenen Aufteilung, wenn sich der Betrag ändert", () => {
    // Gespeicherte 70/30 von 100 €, Betrag wird auf 110 € korrigiert
    const saved = [entry("A", 70), entry("B", 30)];
    expect(redistributeUnlocked(saved, "amount", 110).map((e) => e.value)).toEqual([
      77, 33,
    ]);
    expect(redistributeUnlocked(saved, "amount", 100).map((e) => e.value)).toEqual([
      70, 30,
    ]);
  });

  it("hält das Verhältnis der Übrigen, wenn eine Person fixiert wird", () => {
    const saved = [entry("A", 60, true), entry("B", 30), entry("C", 20)];
    expect(redistributeUnlocked(saved, "amount", 100).map((e) => e.value)).toEqual([
      60, 24, 16,
    ]);
  });

  it("lässt einen fixierten Betrag stehen und gibt den Rest den Übrigen", () => {
    const entries = [entry("A", 30, true), entry("B", 70)];
    expect(redistributeUnlocked(entries, "amount", 200).map((e) => e.value)).toEqual([
      30, 170,
    ]);
  });

  it("behandelt eine faire Aufteilung trotz Rest-Cent weiter als fair", () => {
    const fair = [entry("A", 33.34), entry("B", 33.33), entry("C", 33.33)];
    expect(redistributeUnlocked(fair, "amount", 110).map((e) => e.value)).toEqual(
      distributeEvenly(110, 3),
    );
  });

  it("verteilt mit \"even\" gleichmäßig, auch bei eigener Aufteilung", () => {
    const saved = [entry("A", 70), entry("B", 30)];
    expect(
      redistributeUnlocked(saved, "amount", 100, "even").map((e) => e.value),
    ).toEqual([50, 50]);
  });

  it("lässt Anteile und komplett gelockte Einträge unverändert", () => {
    const shares = [entry("A", 2), entry("B", 1)];
    expect(redistributeUnlocked(shares, "shares", 90)).toEqual(shares);
    const locked = [entry("A", 70, true), entry("B", 20, true)];
    expect(redistributeUnlocked(locked, "percent", 90)).toEqual(locked);
  });
});

describe("resolveSplits und deriveSplitRatio", () => {
  it("liefert {Name: Betrag} inklusive Personen mit Anteil 0", () => {
    const entries = [entry("Kev", 100, true), entry("Anna", 0)];
    const splits = resolveSplits(entries, 20);
    expect(splits).toEqual({ Kev: 20, Anna: 0 });
    expect(deriveSplitRatio(splits, "Kev", 20)).toBe(1);
    expect(deriveSplitRatio(splits, "Anna", 20)).toBe(0);
    expect(deriveSplitRatio(splits, "Tom", 20)).toBe(0);
  });

  it("rechnet Anteile (2 : 1) proportional um", () => {
    expect(resolveSplits([entry("Kev", 2), entry("Anna", 1)], 30)).toEqual({
      Kev: 20,
      Anna: 10,
    });
  });
});

describe("convertMode", () => {
  it("ändert beim Wechsel Prozent → Betrag die Verteilung nicht", () => {
    const percent = [entry("A", 70, true), entry("B", 30)];
    const amount = convertMode(percent, "percent", "amount", 50);
    expect(amount.map((e) => e.value)).toEqual([35, 15]);
    expect(amount.map((e) => e.locked)).toEqual([true, false]);
    expect(convertMode(amount, "amount", "percent", 50).map((e) => e.value)).toEqual([
      70, 30,
    ]);
  });

  it("startet bei Anteilen mit je 1 Anteil ohne Locks", () => {
    const shares = convertMode([entry("A", 70, true), entry("B", 30)], "percent", "shares", 50);
    expect(shares).toEqual([entry("A", 1), entry("B", 1)]);
  });
});

describe("syncEntries", () => {
  it("nimmt neue Personen auf, entfernt entfallene und balanciert neu", () => {
    const entries = [entry("A", 50), entry("B", 50)];
    const next = syncEntries(entries, ["A", "C", "D"], "percent", 90);
    expect(next.map((e) => e.name)).toEqual(["A", "C", "D"]);
    expect(next.map((e) => e.value)).toEqual([33.34, 33.33, 33.33]);
  });

  it("lässt eine eigene Aufteilung stehen: neue Personen starten mit 0", () => {
    const saved = [entry("A", 70), entry("B", 30)];
    const withNew = syncEntries(saved, ["A", "B", "C"], "amount", 100);
    expect(withNew.map((e) => e.value)).toEqual([70, 30, 0]);
    // ... und verschwinden spurlos wieder (Tippen eines neuen Zahlernamens)
    const without = syncEntries(withNew, ["A", "B"], "amount", 100);
    expect(without.map((e) => e.value)).toEqual([70, 30]);
  });

  it("lässt einen gelockten Wert stehen", () => {
    const entries = [entry("A", 60, true), entry("B", 40)];
    const next = syncEntries(entries, ["A", "B", "C"], "percent", 90);
    expect(next.map((e) => e.value)).toEqual([60, 20, 20]);
  });
});

describe("clampValue", () => {
  it("begrenzt je Modus", () => {
    expect(clampValue(150, "percent", 20)).toBe(100);
    expect(clampValue(33.337, "percent", 20)).toBe(33.34);
    expect(clampValue(25, "amount", 20)).toBe(20);
    expect(clampValue(2.6, "shares", 20)).toBe(3);
    expect(clampValue(-1, "amount", 20)).toBe(0);
    expect(clampValue(Number.NaN, "percent", 20)).toBe(0);
  });
});

describe("splitsFromRatio", () => {
  it("bildet das alte split_ratio-Modell summengenau nach", () => {
    const splits = splitsFromRatio(["Kev", "Anna", "Tom"], "Kev", 10, 0.5);
    expect(splits.Kev).toBe(5);
    expect(cents(Object.values(splits))).toBe(1000);
  });

  it("lässt den Zahler alles tragen, wenn er allein ist", () => {
    expect(splitsFromRatio(["Kev"], "Kev", 10, 0.5)).toEqual({ Kev: 10 });
  });
});
