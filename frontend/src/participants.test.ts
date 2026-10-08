import { describe, expect, it } from "vitest";
import { collectParticipants } from "./participants";
import { makeExpense } from "./testExpense";

describe("collectParticipants", () => {
  it("liefert bei leerer Liste niemanden", () => {
    expect(collectParticipants([])).toEqual([]);
  });

  it("nennt Zahler in Reihenfolge des ersten Auftretens, ohne Doppelte", () => {
    const expenses = [
      makeExpense({ payer_name: "Kev" }),
      makeExpense({ payer_name: "Anna" }),
      makeExpense({ payer_name: "Kev" }),
    ];
    expect(collectParticipants(expenses)).toEqual(["Kev", "Anna"]);
  });

  it("stellt die festen Personen der Liste voran, auch ohne eigene Ausgabe", () => {
    expect(collectParticipants([], ["Kev", "Anna", "Tom"])).toEqual([
      "Kev",
      "Anna",
      "Tom",
    ]);
    const expenses = [
      makeExpense({ payer_name: "Max" }),
      makeExpense({ payer_name: "Anna" }),
    ];
    expect(collectParticipants(expenses, ["Kev", "Anna"])).toEqual([
      "Kev",
      "Anna",
      "Max",
    ]);
  });

  it("kennt auch reine Mit-Esser aus einer Aufteilung (auch mit Anteil 0)", () => {
    const expenses = [
      makeExpense({ payer_name: "Kev", splits: { Kev: 5, Tom: 5, Mia: 0 } }),
      makeExpense({ payer_name: "Anna" }),
    ];
    expect(collectParticipants(expenses)).toEqual([
      "Kev",
      "Tom",
      "Mia",
      "Anna",
    ]);
  });
});
