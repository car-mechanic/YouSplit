import { afterEach, describe, expect, it, vi } from "vitest";
import { addExpense, ApiError, DuplicateError, deleteExpense, withReason } from "./api";

function mockFetch(status: number, body: string) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(status === 204 ? null : body, { status })),
  );
}

const expense = { title: "Pizza", amount: 10, payer_name: "Kev", split_ratio: 0.5 };

afterEach(() => vi.unstubAllGlobals());

describe("Fehlerbehandlung des API-Clients", () => {
  it("wirft bei 409 einen DuplicateError mit der Backend-Meldung", async () => {
    mockFetch(409, JSON.stringify({ detail: "Gibt es schon." }));
    const error = await addExpense("list", expense).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(DuplicateError);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).detail).toBe("Gibt es schon.");
  });

  it("reicht die Ursache eines 502 (Wechselkurs) durch", async () => {
    mockFetch(502, JSON.stringify({ detail: "Wechselkurs für USD nicht abrufbar" }));
    const error = await addExpense("list", expense).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).not.toBeInstanceOf(DuplicateError);
    expect((error as ApiError).status).toBe(502);
    expect(withReason("Nicht gespeichert", error)).toBe(
      "Nicht gespeichert: Wechselkurs für USD nicht abrufbar",
    );
  });

  it("hat bei 422 (Feldliste) und Nicht-JSON keine Ursache", async () => {
    mockFetch(422, JSON.stringify({ detail: [{ msg: "field required" }] }));
    const invalid = await addExpense("list", expense).catch((e: unknown) => e);
    expect((invalid as ApiError).detail).toBeNull();
    expect((invalid as ApiError).message).toBe("API-Fehler 422");

    mockFetch(500, "Internal Server Error");
    const broken = await addExpense("list", expense).catch((e: unknown) => e);
    expect((broken as ApiError).detail).toBeNull();
    expect(withReason("Nicht gespeichert", broken)).toBe("Nicht gespeichert.");
  });

  it("liefert bei Erfolg den Body, bei 204 nichts", async () => {
    mockFetch(201, JSON.stringify({ id: "1" }));
    await expect(addExpense("list", expense)).resolves.toEqual({ id: "1" });
    mockFetch(204, "");
    await expect(deleteExpense("list", "1")).resolves.toBeUndefined();
  });
});

describe("withReason", () => {
  it("bleibt bei Netzwerkfehlern (kein ApiError) bei der Grundmeldung", () => {
    expect(withReason("Nicht gespeichert", new TypeError("Failed to fetch"))).toBe(
      "Nicht gespeichert.",
    );
  });
});
