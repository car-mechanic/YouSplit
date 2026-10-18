import { useEffect, useState } from "react";
import { getHaUsers, getMe, withReason } from "./api";
import type { CurrentUser, HaUserOption } from "./api";

/**
 * Angemeldeter Home-Assistant-Benutzer (nur über Ingress, sonst null).
 *
 * Einmal pro Seitenaufruf abgefragt: der Benutzer wechselt nicht, ohne dass
 * Home Assistant die Seite neu lädt. Ein Fehler zählt als „kein Benutzer“,
 * dann läuft die App wie ohne Home Assistant.
 */
let mePromise: Promise<CurrentUser | null> | null = null;

export function loadMe(): Promise<CurrentUser | null> {
  mePromise ??= getMe().catch(() => null);
  return mePromise;
}

/** `undefined`, solange die Abfrage läuft. */
export function useMe(): CurrentUser | null | undefined {
  const [me, setMe] = useState<CurrentUser | null | undefined>(undefined);
  useEffect(() => {
    let ignore = false;
    void loadMe().then((user) => {
      if (!ignore) setMe(user);
    });
    return () => {
      ignore = true;
    };
  }, []);
  return me;
}

interface HaUsersState {
  users: HaUserOption[];
  error: string | null;
}

/** HA-Benutzer für die Personen-Auswahl; nur abgefragt, wenn `enabled`. */
export function useHaUsers(enabled: boolean): HaUsersState {
  const [state, setState] = useState<HaUsersState>({ users: [], error: null });
  useEffect(() => {
    if (!enabled) return;
    let ignore = false;
    getHaUsers()
      .then((users) => {
        if (!ignore) setState({ users, error: null });
      })
      .catch((error: unknown) => {
        if (!ignore) {
          setState({
            users: [],
            error: withReason("Home-Assistant-Benutzer nicht abrufbar", error),
          });
        }
      });
    return () => {
      ignore = true;
    };
  }, [enabled]);
  return state;
}
