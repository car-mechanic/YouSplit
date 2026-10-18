import type { HaUserOption, MemberUsers, MembersValue } from "./api";

/**
 * Personen einer Liste und ihre Verknüpfung mit Home-Assistant-Benutzern.
 *
 * Personen bleiben Namen (Ausgaben verweisen über `payer_name`/`splits` auf
 * Namen). Die Verknüpfung {Name: Benutzer-ID} sorgt dafür, dass der Benutzer
 * die Liste auf jedem Gerät sieht und als Zahler vorgeschlagen wird. Ein
 * Benutzer ist höchstens eine Person (prüft auch das Backend).
 */

/** Name der Person, die mit dem Benutzer verknüpft ist, sonst null. */
export function linkedName(
  memberUsers: MemberUsers,
  userId: string | undefined,
): string | null {
  if (!userId) return null;
  const entry = Object.entries(memberUsers).find(([, id]) => id === userId);
  return entry ? entry[0] : null;
}

/** Eingetippten Namen aufnehmen (getrimmt, ohne Doppelte). */
export function addName(value: MembersValue, raw: string): MembersValue {
  const name = raw.trim();
  if (!name || value.members.includes(name)) return value;
  return { ...value, members: [...value.members, name] };
}

/**
 * HA-Benutzer als Person aufnehmen. Gibt es den Namen schon unverknüpft, ist
 * das sehr wahrscheinlich dieselbe Person: dann nur verknüpfen. Gehört der
 * Name schon einem anderen Benutzer, bekommt der neue einen Zusatz.
 */
export function addHaUser(value: MembersValue, user: HaUserOption): MembersValue {
  if (linkedName(value.memberUsers, user.id) !== null) return value;
  const base = user.name.trim();
  let name = base;
  for (let n = 2; value.memberUsers[name] !== undefined; n++) {
    name = `${base} (${n})`;
  }
  const members = value.members.includes(name)
    ? value.members
    : [...value.members, name];
  return { members, memberUsers: { ...value.memberUsers, [name]: user.id } };
}

/** Person entfernen, ihre Verknüpfung gleich mit. */
export function removeMember(value: MembersValue, name: string): MembersValue {
  const memberUsers = { ...value.memberUsers };
  delete memberUsers[name];
  return {
    members: value.members.filter((member) => member !== name),
    memberUsers,
  };
}

/**
 * „Das bin ich“: verknüpft den Benutzer mit der Person und löst eine frühere
 * Verknüpfung desselben Benutzers. Gehört die Person einem anderen Benutzer,
 * bleibt alles unverändert.
 */
export function linkSelf(
  value: MembersValue,
  name: string,
  userId: string,
): MembersValue {
  const owner = value.memberUsers[name];
  if (owner !== undefined && owner !== userId) return value;
  const memberUsers = Object.fromEntries(
    Object.entries(value.memberUsers).filter(([, id]) => id !== userId),
  );
  return { ...value, memberUsers: { ...memberUsers, [name]: userId } };
}

/** HA-Benutzer, die noch nicht als Person der Liste verknüpft sind. */
export function unlinkedUsers(
  users: readonly HaUserOption[],
  value: MembersValue,
): HaUserOption[] {
  const linked = new Set(Object.values(value.memberUsers));
  return users.filter((user) => !linked.has(user.id));
}

/** Gleicher Stand? (Reihenfolge der Personen zählt, die der Links nicht.) */
export function sameMembers(a: MembersValue, b: MembersValue): boolean {
  const links = (value: MembersValue) =>
    JSON.stringify(Object.entries(value.memberUsers).sort());
  return (
    a.members.join("\n") === b.members.join("\n") && links(a) === links(b)
  );
}
