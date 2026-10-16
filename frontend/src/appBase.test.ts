import { describe, expect, it } from "vitest";
import { routerBasename, shareableUrl } from "./appBase";

const INGRESS_BASE = "https://ha.example.org/api/hassio_ingress/AbC123/";

describe("routerBasename", () => {
  it("ist leer bei direktem Aufruf", () => {
    expect(routerBasename("http://ha.local:8099/")).toBe("");
  });

  it("ist das Ingress-Präfix im Ingress", () => {
    expect(routerBasename(INGRESS_BASE)).toBe("/api/hassio_ingress/AbC123");
  });
});

describe("shareableUrl", () => {
  it("nimmt ohne public_url die aktuelle Adresse", () => {
    const href = "http://ha.local:8099/list/42";
    expect(shareableUrl(href, "http://ha.local:8099/", "")).toBe(href);
  });

  it("tauscht im Ingress das HA-Präfix gegen die public_url", () => {
    const href = INGRESS_BASE + "list/42?x=1#a";
    expect(shareableUrl(href, INGRESS_BASE, "https://split.example.org/")).toBe(
      "https://split.example.org/list/42?x=1#a",
    );
  });

  it("nutzt die public_url auch bei direktem Aufruf", () => {
    expect(
      shareableUrl("http://ha.local:8099/list/42", "http://ha.local:8099/", "https://split.example.org"),
    ).toBe("https://split.example.org/list/42");
  });
});
