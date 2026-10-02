/**
 * Reine Berechnungslogik des Advanced Splitters (Roadmap 3.0 #3).
 *
 * Bewusst OHNE React/DOM-Bezug: alle Funktionen sind pur (gleiche Eingabe →
 * gleiche Ausgabe, keine Seiteneffekte) und damit isoliert testbar. Die
 * Komponente `AdvancedSplitter.tsx` hält nur den Zustand und ruft diese Helfer.
 *
 * Zentrale Invariante: `resolveAmounts` liefert Pro-Person-Beträge, deren Summe
 * IMMER exakt dem Gesamtbetrag entspricht — der durch Rundung entstehende
 * Rest-Cent ("1-Cent-Problem") wird der ersten *ungelockten* Person zugewiesen.
 *
 * Locking-Konvention: `locked === true` heißt "vom Nutzer manuell gesetzt".
 * Ungelockte Einträge werden automatisch gleichmäßig aus dem Restbetrag
 * aufgefüllt — sie tragen also immer den fairen Anteil dessen, was nach den
 * gelockten Werten übrig bleibt.
 */

import type { Splits } from "./api";

/** Eingabemodus des Splitters. */
export type SplitMode = "percent" | "amount" | "shares";

/** Anzeige-Reihenfolge der Modi im Dropdown. */
export const SPLIT_MODES: readonly SplitMode[] = ["percent", "amount", "shares"];

/** Ein Teilnehmer-Eintrag im aktuellen Modus. */
export interface SplitEntry {
  name: string;
  /** Bedeutung je nach Modus: Prozent (0–100), Betrag (Währung) oder Anteile. */
  value: number;
  /** true = manuell gesetzt (gelockt); false = automatisch balanciert. */
  locked: boolean;
}

/** Kaufmännisch auf 2 Nachkommastellen runden (Cent-genau). */
export function round2(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

/**
 * Der "Gesamtwert" eines Modus, auf den sich die ungelockten Einträge aufteilen:
 * 100 (Prozent) bzw. der Betrag (Währung). Im Anteile-Modus gibt es keinen festen
 * Gesamtwert (Anteile sind relative Gewichte) → `null`.
 */
function modeTotal(mode: SplitMode, amount: number): number | null {
  if (mode === "percent") return 100;
  if (mode === "amount") return round2(amount);
  return null;
}

/**
 * Verteilt `total` möglichst gleichmäßig auf `count` Positionen (auf Cent
 * gerundet). Der Rundungsrest wird der Position `remainderIndex` zugeschlagen,
 * damit die Summe EXAKT `total` ergibt (das "1-Cent-Problem").
 */
export function distributeEvenly(
  total: number,
  count: number,
  remainderIndex = 0,
): number[] {
  if (count <= 0) return [];
  const base = round2(total / count);
  const values = new Array<number>(count).fill(base);
  const remainder = round2(total - base * count);
  const target = Math.min(Math.max(remainderIndex, 0), count - 1);
  values[target] = round2(values[target] + remainder);
  return values;
}

/** Index der ersten ungelockten Person, sonst 0 (Fallback: erste Person). */
export function firstUnlockedIndex(entries: SplitEntry[]): number {
  const index = entries.findIndex((entry) => !entry.locked);
  return index >= 0 ? index : 0;
}

/**
 * Wählt die Position, die den Rundungsrest ("1-Cent-Problem") aufnimmt. Regel:
 * erste ungelockte Person. Ist der Rest negativ (kann bei Über-Constraint durch
 * Locks vorkommen), wird eine ungelockte Position gewählt, deren Wert den Abzug
 * ohne Unterschreiten von 0 trägt — sonst die größte Position. So bleibt KEIN
 * Anteil negativ (das Backend lehnt negative Beträge ab).
 */
function pickRemainderIndex(
  values: number[],
  entries: SplitEntry[],
  remainder: number,
): number {
  const first = firstUnlockedIndex(entries);
  if (remainder >= 0) return first;
  for (let i = 0; i < values.length; i++) {
    if (!entries[i].locked && values[i] >= -remainder) return i;
  }
  let maxIndex = 0;
  values.forEach((value, index) => {
    if (value > values[maxIndex]) maxIndex = index;
  });
  return maxIndex;
}

/**
 * Verteilt den nach den gelockten Werten verbleibenden Rest gleichmäßig auf die
 * ungelockten Einträge (Prozent-/Betrag-Modus). Damit gilt: Lockt der Nutzer
 * eine Person auf einen Wert, teilen sich alle übrigen den Rest — zieht man bei
 * X ab, bekommen die Ungelockten automatisch mehr (und umgekehrt).
 *
 * Im Anteile-Modus (kein fester Gesamtwert) bleiben die Einträge unverändert.
 */
export function redistributeUnlocked(
  entries: SplitEntry[],
  mode: SplitMode,
  amount: number,
): SplitEntry[] {
  const total = modeTotal(mode, amount);
  const next = entries.map((entry) => ({ ...entry }));
  if (total === null) return next;

  const unlocked = next.filter((entry) => !entry.locked);
  if (unlocked.length === 0) return next; // alles gelockt → nichts zu verteilen

  const lockedSum = next
    .filter((entry) => entry.locked)
    .reduce((sum, entry) => sum + entry.value, 0);
  const remaining = Math.max(0, round2(total - lockedSum));
  // Rest-Cent geht an die erste ungelockte Person (Index 0 der Ungelockten).
  const shares = distributeEvenly(remaining, unlocked.length, 0);

  let k = 0;
  for (const entry of next) {
    if (!entry.locked) entry.value = shares[k++];
  }
  return next;
}

/**
 * Faire Startverteilung für `names` im gegebenen Modus (alle ungelockt):
 * - Prozent: 100 % gleichmäßig (z. B. 4 Personen → 25 % je).
 * - Betrag: `amount` gleichmäßig.
 * - Anteile: je 1 Anteil.
 */
export function fairEntries(
  names: string[],
  mode: SplitMode,
  amount: number,
): SplitEntry[] {
  if (mode === "shares") {
    return names.map((name) => ({ name, value: 1, locked: false }));
  }
  const total = mode === "percent" ? 100 : round2(amount);
  const values = distributeEvenly(total, names.length, 0);
  return names.map((name, index) => ({
    name,
    value: values[index] ?? 0,
    locked: false,
  }));
}

/**
 * Löst die Einträge in konkrete Pro-Person-Beträge (in der Erfassungswährung)
 * auf. Die Summe entspricht IMMER exakt `amount`; der Rest-Cent geht an die
 * erste ungelockte Person.
 *
 * Die Auflösung ist modus-unabhängig: In jedem Modus sind die Werte
 * nicht-negative Gewichte (Prozent, Betrag oder Anteile), die proportional auf
 * `amount` normiert werden. Das macht das Ergebnis robust gegen Über-Constraint
 * (z. B. Locks, die zusammen über 100 % liegen) — es entstehen nie negative
 * Anteile, und die Summe stimmt exakt.
 */
export function resolveAmounts(entries: SplitEntry[], amount: number): number[] {
  const count = entries.length;
  if (count === 0) return [];
  const target = round2(amount);

  const weights = entries.map((entry) => Math.max(0, entry.value));
  const weightSum = weights.reduce((sum, weight) => sum + weight, 0);
  const scaled =
    weightSum > 0
      ? weights.map((weight) => (weight * target) / weightSum)
      : distributeEvenly(target, count, 0);

  const rounded = scaled.map(round2);
  const sum = rounded.reduce((acc, value) => acc + value, 0);
  const remainder = round2(target - sum);
  const fixIndex = pickRemainderIndex(rounded, entries, remainder);
  rounded[fixIndex] = round2(rounded[fixIndex] + remainder);
  return rounded;
}

/**
 * Baut aus den Einträgen die Backend-Aufteilung {Name: Betrag} — inklusive
 * Personen mit Anteil 0 (sie sind bewusst Teilnehmer der Ausgabe).
 */
export function resolveSplits(entries: SplitEntry[], amount: number): Splits {
  const amounts = resolveAmounts(entries, amount);
  const splits: Splits = {};
  entries.forEach((entry, index) => {
    splits[entry.name] = amounts[index];
  });
  return splits;
}

/**
 * Eigenanteil des Zahlers als Verhältnis (0–1) für das Fallback-Feld
 * `split_ratio`. Hält die Altdaten-Anzeige ("trägt X %") kohärent, auch wenn die
 * maßgebliche Wahrheit die `splits` sind.
 */
export function deriveSplitRatio(splits: Splits, payerName: string, amount: number): number {
  if (amount <= 0) return 0.5;
  const payerShare = splits[payerName] ?? 0;
  const ratio = payerShare / amount;
  return Math.min(1, Math.max(0, ratio));
}

/**
 * Autokorrektur beim Verlassen eines Feldes (onBlur): begrenzt und rundet einen
 * Wert passend zum Modus.
 * - Prozent: [0, 100], 2 Nachkommastellen.
 * - Betrag: [0, amount] (eine Person kann nicht mehr als den Gesamtbetrag
 *   verbrauchen), 2 Nachkommastellen.
 * - Anteile: ganzzahlig, >= 0.
 */
export function clampValue(value: number, mode: SplitMode, amount: number): number {
  if (!Number.isFinite(value) || value < 0) value = 0;
  if (mode === "percent") return round2(Math.min(100, value));
  if (mode === "amount") return round2(Math.min(round2(amount), value));
  return Math.max(0, Math.round(value)); // Anteile: ganze Zahlen
}

/**
 * Synchronisiert die Einträge auf die aktuelle Teilnehmerliste `names`: bereits
 * bekannte Namen behalten ihren Wert/Lock, neue kommen hinzu, entfallene fliegen
 * raus. Anschließend werden die ungelockten Einträge neu ausbalanciert, damit
 * die Aufteilung stimmig bleibt (im Anteile-Modus erhalten neue Personen 1
 * Anteil).
 */
export function syncEntries(
  entries: SplitEntry[],
  names: string[],
  mode: SplitMode,
  amount: number,
): SplitEntry[] {
  const next: SplitEntry[] = names.map((name) => {
    const existing = entries.find((entry) => entry.name === name);
    if (existing) return { ...existing };
    // Neuer Teilnehmer: im Anteile-Modus 1 Anteil, sonst 0 (wird gleich neu
    // ausbalanciert, da ungelockt).
    return { name, value: mode === "shares" ? 1 : 0, locked: false };
  });
  return redistributeUnlocked(next, mode, amount);
}

/**
 * Wechselt den Eingabemodus und rechnet die aktuelle Aufteilung proportional um,
 * damit der Wechsel die tatsächliche Kostenverteilung nicht verändert.
 * Ausnahme: Der Wechsel ZU "Anteile" startet bewusst mit fairen 1-Anteilen —
 * die anderen Modi kennen keine natürliche Ganzzahl-Entsprechung, und "Anteile"
 * lädt zum Neu-Eintippen einfacher Gewichte (z. B. 2 : 1) ein.
 */
export function convertMode(
  entries: SplitEntry[],
  fromMode: SplitMode,
  toMode: SplitMode,
  amount: number,
): SplitEntry[] {
  if (fromMode === toMode) return entries.map((entry) => ({ ...entry }));
  if (toMode === "shares") {
    return entries.map((entry) => ({ name: entry.name, value: 1, locked: false }));
  }

  const amounts = resolveAmounts(entries, amount);
  // Beim Wechsel VON Anteilen sind die Locks bedeutungslos → zurücksetzen.
  const keepLock = fromMode !== "shares";
  const target = round2(amount);

  return entries.map((entry, index) => ({
    name: entry.name,
    value:
      toMode === "amount"
        ? amounts[index]
        : target > 0
          ? round2((100 * amounts[index]) / target)
          : 0,
    locked: keepLock ? entry.locked : false,
  }));
}

/**
 * Initialisiert Einträge aus einer bestehenden Backend-Aufteilung (Betrag-Modus)
 * — genutzt beim Bearbeiten einer gespeicherten Ausgabe. Namen ohne Anteil
 * erhalten 0.
 */
export function entriesFromSplits(
  splits: Splits,
  names: string[],
): SplitEntry[] {
  return names.map((name) => ({
    name,
    value: round2(splits[name] ?? 0),
    locked: false,
  }));
}

/** Summe der aktuellen Werte (für die Live-Anzeige "Summe: … %/…€"). */
export function sumValues(entries: SplitEntry[]): number {
  return round2(entries.reduce((sum, entry) => sum + entry.value, 0));
}

/**
 * Rekonstruiert eine Pro-Person-Aufteilung aus dem alten `split_ratio`-Modell:
 * Der Zahler trägt `ratio · amount`, der Rest wird gleichmäßig auf die übrigen
 * Teilnehmer verteilt (1-Cent-Rest an die erste andere Person). Genutzt beim
 * Bearbeiten von Altdaten/gescannten Bons ohne explizite `splits`, damit deren
 * bisherige Aufteilung TREU vorbelegt wird (statt sie still auf fair-% zu ändern).
 */
export function splitsFromRatio(
  participants: string[],
  payerName: string,
  amount: number,
  ratio: number,
): Splits {
  const target = round2(amount);
  const splits: Splits = {};
  const others = participants.filter((name) => name !== payerName);

  if (others.length === 0) {
    // Nur der Zahler ist bekannt → er trägt alles selbst.
    for (const name of participants) {
      splits[name] = name === payerName ? target : 0;
    }
    return splits;
  }

  const safeRatio = Math.min(1, Math.max(0, ratio));
  const payerShare = round2(target * safeRatio);
  const restShares = distributeEvenly(round2(target - payerShare), others.length, 0);
  splits[payerName] = payerShare;
  others.forEach((name, index) => {
    splits[name] = restShares[index];
  });
  // Sicherheitshalber alle Teilnehmer abdecken (falls Zahler nicht in der Liste).
  for (const name of participants) {
    if (!(name in splits)) splits[name] = 0;
  }
  return splits;
}
