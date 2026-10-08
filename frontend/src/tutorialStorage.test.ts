import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { payerStorageKey } from "./payerStorage";
import { markTutorialDone, shouldShowTutorial } from "./tutorialStorage";

function memoryStorage(): Storage {
  const data = new Map<string, string>();
  return {
    get length() {
      return data.size;
    },
    clear: () => data.clear(),
    getItem: (key) => data.get(key) ?? null,
    key: (index) => [...data.keys()][index] ?? null,
    removeItem: (key) => void data.delete(key),
    setItem: (key, value) => void data.set(key, String(value)),
  };
}

beforeEach(() => vi.stubGlobal("localStorage", memoryStorage()));
afterEach(() => vi.unstubAllGlobals());

describe("shouldShowTutorial", () => {
  it("zeigt das Tutorial beim ersten Öffnen einer Liste, danach nicht mehr", () => {
    expect(shouldShowTutorial("a")).toBe(true);
    markTutorialDone("a");
    expect(shouldShowTutorial("a")).toBe(false);
  });

  it("gilt je Liste", () => {
    markTutorialDone("a");
    expect(shouldShowTutorial("b")).toBe(true);
  });

  it("überspringt Listen, die auf dem Gerät schon benutzt werden", () => {
    localStorage.setItem(payerStorageKey("alt"), "Kev");
    expect(shouldShowTutorial("alt")).toBe(false);
  });

  it("zeigt ohne verfügbaren Speicher kein Tutorial (statt bei jedem Aufruf)", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("blockiert");
      },
    });
    expect(shouldShowTutorial("a")).toBe(false);
    expect(() => markTutorialDone("a")).not.toThrow();
  });
});
