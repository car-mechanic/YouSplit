import { describe, expect, it } from "vitest";
import { sortExpenses } from "./expenseSort";
import { makeExpense } from "./testExpense";

const titles = (expenses: { title: string }[]) => expenses.map((e) => e.title);

describe("sortExpenses", () => {
  // "nachgetragen" wurde zuletzt angelegt, gehört aber zum ältesten Tag
  const expenses = [
    makeExpense({
      title: "alt",
      receipt_date: "2026-08-10",
      created_at: "2026-08-10T09:00:00+00:00",
    }),
    makeExpense({
      title: "neu",
      receipt_date: "2026-08-12",
      created_at: "2026-08-12T09:00:00+00:00",
    }),
    makeExpense({
      title: "nachgetragen",
      receipt_date: "2026-08-01",
      created_at: "2026-08-13T09:00:00+00:00",
    }),
  ];

  it("sortiert nach dem angezeigten Datum, nicht nach dem Anlagezeitpunkt", () => {
    expect(titles(sortExpenses(expenses, "date-desc"))).toEqual([
      "neu",
      "alt",
      "nachgetragen",
    ]);
    expect(titles(sortExpenses(expenses, "date-asc"))).toEqual([
      "nachgetragen",
      "alt",
      "neu",
    ]);
  });

  it("nutzt ohne receipt_date den Anlagetag", () => {
    const mixed = [
      makeExpense({ title: "manuell", created_at: "2026-08-11T22:00:00+00:00" }),
      ...expenses,
    ];
    expect(titles(sortExpenses(mixed, "date-desc"))).toEqual([
      "neu",
      "manuell",
      "alt",
      "nachgetragen",
    ]);
  });

  it("ordnet Ausgaben desselben Tags nach dem Anlegen", () => {
    const sameDay = [
      makeExpense({
        title: "zweite",
        receipt_date: "2026-08-10",
        created_at: "2026-08-14T09:00:02+00:00",
      }),
      makeExpense({
        title: "erste",
        receipt_date: "2026-08-10",
        created_at: "2026-08-14T09:00:01+00:00",
      }),
    ];
    expect(titles(sortExpenses(sameDay, "date-asc"))).toEqual(["erste", "zweite"]);
    expect(titles(sortExpenses(sameDay, "date-desc"))).toEqual(["zweite", "erste"]);
  });

  it("vergleicht Beträge in EUR über den Wechselkurs", () => {
    const amounts = [
      makeExpense({ title: "45 EUR", amount: 45 }),
      // 50 USD zum Kurs 0,85 sind 42,50 EUR und damit günstiger als 45 EUR
      makeExpense({ title: "50 USD", amount: 50, currency: "USD", exchange_rate: 0.85 }),
      makeExpense({ title: "10 EUR", amount: 10 }),
    ];
    expect(titles(sortExpenses(amounts, "amount-desc"))).toEqual([
      "45 EUR",
      "50 USD",
      "10 EUR",
    ]);
    expect(titles(sortExpenses(amounts, "amount-asc"))).toEqual([
      "10 EUR",
      "50 USD",
      "45 EUR",
    ]);
  });

  it("lässt die Eingabe unverändert", () => {
    const before = titles(expenses);
    sortExpenses(expenses, "date-asc");
    expect(titles(expenses)).toEqual(before);
  });
});
