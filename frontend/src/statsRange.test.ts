import { describe, expect, it } from "vitest";
import {
  availableMonths,
  filterByRange,
  isInRange,
  monthLabel,
} from "./statsRange";
import { makeExpense } from "./testExpense";

const expenses = [
  makeExpense({ title: "Juni-Anfang", receipt_date: "2026-06-01" }),
  makeExpense({ title: "Juni-Mitte", receipt_date: "2026-06-15" }),
  makeExpense({ title: "Juni-Ende", receipt_date: "2026-06-30" }),
  makeExpense({ title: "Juli", receipt_date: "2026-07-20" }),
  // ohne receipt_date zählt der Anlagetag
  makeExpense({
    title: "Januar",
    receipt_date: null,
    created_at: "2026-01-10T08:00:00+00:00",
  }),
];
const titles = (list: { title: string }[]) => list.map((e) => e.title);

describe("availableMonths", () => {
  it("liefert jeden Monat mit Ausgaben einmal, neueste zuerst", () => {
    expect(availableMonths(expenses)).toEqual([
      "2026-07",
      "2026-06",
      "2026-01",
    ]);
    expect(availableMonths([])).toEqual([]);
  });
});

describe("monthLabel", () => {
  it("schreibt den Monat aus", () => {
    expect(monthLabel("2026-06")).toBe("Juni 2026");
    expect(monthLabel("2027-01")).toBe("Januar 2027");
  });
});

describe("filterByRange", () => {
  it("lässt bei 'alles' nichts weg", () => {
    expect(filterByRange(expenses, { kind: "all" })).toHaveLength(5);
  });

  it("nimmt bei einem Monat genau dessen Tage", () => {
    expect(
      titles(filterByRange(expenses, { kind: "month", month: "2026-06" })),
    ).toEqual(["Juni-Anfang", "Juni-Mitte", "Juni-Ende"]);
    expect(
      titles(filterByRange(expenses, { kind: "month", month: "2026-01" })),
    ).toEqual(["Januar"]);
  });

  it("zählt beim eigenen Zeitraum beide Grenztage mit", () => {
    const range = {
      kind: "custom",
      from: "2026-06-15",
      to: "2026-07-20",
    } as const;
    expect(titles(filterByRange(expenses, range))).toEqual([
      "Juni-Mitte",
      "Juni-Ende",
      "Juli",
    ]);
  });

  it("dreht einen verdrehten Zeitraum richtig herum", () => {
    expect(
      isInRange("2026-06-20", {
        kind: "custom",
        from: "2026-06-25",
        to: "2026-06-15",
      }),
    ).toBe(true);
  });

  it("liefert bei einem leeren Zeitraum nichts", () => {
    expect(
      filterByRange(expenses, {
        kind: "custom",
        from: "2026-03-01",
        to: "2026-03-31",
      }),
    ).toEqual([]);
  });
});
