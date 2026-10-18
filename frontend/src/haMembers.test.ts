import { describe, expect, it } from "vitest";
import {
  addHaUser,
  addName,
  linkedName,
  linkSelf,
  removeMember,
  sameMembers,
  unlinkedUsers,
} from "./haMembers";

const kev = { id: "u-kev", name: "Kev" };
const anna = { id: "u-anna", name: "Anna" };

describe("Personen mit HA-Benutzern verknüpfen", () => {
  it("findet den Namen eines verknüpften Benutzers", () => {
    expect(linkedName({ Kev: "u-kev" }, "u-kev")).toBe("Kev");
    expect(linkedName({ Kev: "u-kev" }, "u-anna")).toBeNull();
    expect(linkedName({ Kev: "u-kev" }, undefined)).toBeNull();
  });

  it("nimmt eingetippte Namen getrimmt und ohne Doppelte auf", () => {
    const value = addName({ members: ["Kev"], memberUsers: {} }, " Anna ");
    expect(value.members).toEqual(["Kev", "Anna"]);
    expect(addName(value, "Kev")).toBe(value);
    expect(addName(value, "  ")).toBe(value);
  });

  it("nimmt einen HA-Benutzer als neue Person auf", () => {
    expect(addHaUser({ members: ["Tom"], memberUsers: {} }, kev)).toEqual({
      members: ["Tom", "Kev"],
      memberUsers: { Kev: "u-kev" },
    });
  });

  it("verknüpft einen gleichnamigen, freien Eintrag statt ihn zu doppeln", () => {
    expect(addHaUser({ members: ["Kev"], memberUsers: {} }, kev)).toEqual({
      members: ["Kev"],
      memberUsers: { Kev: "u-kev" },
    });
  });

  it("gibt gleichnamigen Benutzern einen Zusatz", () => {
    const value = addHaUser(
      { members: ["Kev"], memberUsers: { Kev: "u-other" } },
      kev,
    );
    expect(value.members).toEqual(["Kev", "Kev (2)"]);
    expect(value.memberUsers["Kev (2)"]).toBe("u-kev");
  });

  it("nimmt denselben Benutzer nicht zweimal auf", () => {
    const value = { members: ["Kevin"], memberUsers: { Kevin: "u-kev" } };
    expect(addHaUser(value, kev)).toBe(value);
  });

  it("entfernt eine Person samt Verknüpfung", () => {
    expect(
      removeMember(
        { members: ["Kev", "Anna"], memberUsers: { Kev: "u-kev", Anna: "u-anna" } },
        "Kev",
      ),
    ).toEqual({ members: ["Anna"], memberUsers: { Anna: "u-anna" } });
  });

  it("„Das bin ich“ verlegt die eigene Verknüpfung", () => {
    const value = linkSelf(
      { members: ["Kev", "Kevin"], memberUsers: { Kev: "u-kev" } },
      "Kevin",
      "u-kev",
    );
    expect(value.memberUsers).toEqual({ Kevin: "u-kev" });
  });

  it("„Das bin ich“ übernimmt keine fremde Person", () => {
    const value = { members: ["Anna"], memberUsers: { Anna: "u-anna" } };
    expect(linkSelf(value, "Anna", "u-kev")).toBe(value);
  });

  it("bietet nur noch nicht verknüpfte Benutzer an", () => {
    expect(
      unlinkedUsers([kev, anna], { members: ["Kev"], memberUsers: { Kev: "u-kev" } }),
    ).toEqual([anna]);
  });

  it("vergleicht Stände unabhängig von der Reihenfolge der Verknüpfungen", () => {
    const a = { members: ["Kev", "Anna"], memberUsers: { Kev: "1", Anna: "2" } };
    const b = { members: ["Kev", "Anna"], memberUsers: { Anna: "2", Kev: "1" } };
    expect(sameMembers(a, b)).toBe(true);
    expect(sameMembers(a, { ...b, members: ["Anna", "Kev"] })).toBe(false);
    expect(sameMembers(a, { ...b, memberUsers: { Kev: "1" } })).toBe(false);
  });
});
