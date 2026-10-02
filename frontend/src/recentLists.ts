/**
 * Zuletzt besuchte Listen im `localStorage` (Roadmap 3.0 #1).
 *
 * YouSplit hat bewusst kein Login: die Listen-UUID ist der einzige Zugang. Damit
 * man seine Listen auf einem Gerät wiederfindet, merken wir hier pro Gerät die
 * besuchten Listen (UUID + Titel + letzter Besuch) — rein lokal, nichts verlässt
 * den Browser. Gekapselt in einem Modul, damit kein anderer Code direkt auf den
 * Storage-Key zugreift.
 */

const STORAGE_KEY = "yousplit:recent_lists";
// Deckel gegen unbegrenztes Wachstum; ältere Einträge fallen hinten heraus.
const MAX_RECENT = 12;

export interface RecentList {
  id: string;
  title: string;
  /** Letzter Besuch als ISO-Zeitstempel (sortierbar, an formatDate übergebbar). */
  lastVisit: string;
}

/** Liest die besuchten Listen, neueste zuerst. Defensiv gegen kaputtes JSON. */
export function getRecentLists(): RecentList[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    // Nur wohlgeformte Einträge übernehmen (Storage könnte manipuliert sein).
    const valid = parsed.filter(
      (item): item is RecentList =>
        typeof item === "object" &&
        item !== null &&
        typeof (item as RecentList).id === "string" &&
        typeof (item as RecentList).title === "string" &&
        typeof (item as RecentList).lastVisit === "string",
    );
    return valid.sort((a, b) => b.lastVisit.localeCompare(a.lastVisit));
  } catch {
    return [];
  }
}

/**
 * Markiert eine Liste als (gerade) besucht: aktualisiert Titel + Zeitstempel oder
 * legt den Eintrag neu an und schiebt ihn nach vorne.
 */
export function addRecentList(id: string, title: string): void {
  const now = new Date().toISOString();
  const others = getRecentLists().filter((item) => item.id !== id);
  const next = [{ id, title, lastVisit: now }, ...others].slice(0, MAX_RECENT);
  persist(next);
}

/** Entfernt eine Liste aus der Merkliste (nur lokal – die Liste bleibt bestehen). */
export function removeRecentList(id: string): void {
  persist(getRecentLists().filter((item) => item.id !== id));
}

function persist(lists: RecentList[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(lists));
  } catch {
    // Storage voll / nicht verfügbar (privater Modus) → still ignorieren,
    // die Merkliste ist ein Komfort-Feature, kein Muss.
  }
}
