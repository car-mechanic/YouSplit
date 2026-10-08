import { useImperativeHandle, useMemo, useState } from "react";
import type { Ref } from "react";
import { Lock, Unlock } from "lucide-react";
import type { Splits } from "../api";
import { formatMoney, parseAmount } from "../format";
import {
  clampValue,
  convertMode,
  deriveSplitRatio,
  entriesFromSplits,
  fairEntries,
  redistributeUnlocked,
  resolveAmounts,
  resolveSplits,
  sumValues,
  syncEntries,
} from "../splitMath";
import type { SplitEntry, SplitMode } from "../splitMath";

/** Vom Elternformular beim Speichern abgerufenes Ergebnis. */
export interface AdvancedSplitterHandle {
  getResult: () => { splits: Splits; splitRatio: number };
}

interface AdvancedSplitterProps {
  /** Alle anzuzeigenden Teilnehmer (Zahler + bekannte Personen der Liste). */
  participants: string[];
  /** Gesamtbetrag der Ausgabe in der Erfassungswährung (0, wenn noch leer). */
  amount: number;
  /** Erfassungswährung – nur für die Betrags-Vorschau je Person. */
  currency: string;
  /** Name des Zahlers – für die Ableitung von split_ratio (Fallback). */
  payerName: string;
  /** Bestehende Aufteilung beim Bearbeiten (startet dann im Betrag-Modus). */
  initialSplits?: Splits | null;
  ref?: Ref<AdvancedSplitterHandle>;
}

// Dropdown-Beschriftung der Modi.
const MODE_LABELS: Record<SplitMode, string> = {
  percent: "Prozent",
  amount: "Betrag",
  shares: "Anteile",
};

// Einheit hinter dem Eingabefeld je Modus.
function unitLabel(mode: SplitMode, currency: string): string {
  if (mode === "percent") return "%";
  if (mode === "amount") return currency;
  return "Anteile";
}

// Wert für das Eingabefeld formatieren: deutsches Dezimalkomma, ganze Zahlen
// ohne Nachkommastellen; Anteile stets ganzzahlig.
function formatValue(value: number, mode: SplitMode): string {
  if (mode === "shares") return String(Math.max(0, Math.round(value)));
  return Number.isInteger(value) ? String(value) : value.toString().replace(".", ",");
}

/**
 * Advanced Splitter (Roadmap 3.0 #3): steuert die Kostenaufteilung einer Ausgabe
 * über ALLE bekannten Teilnehmer – auch solche, die 0 zahlen.
 *
 * Drei Modi (Prozent, Betrag, Anteile). Ändert der Nutzer einen Wert, wird die
 * Person „gelockt“ und die restlichen (ungelockten) Teilnehmer teilen sich den
 * Rest gleichmäßig auf (die eigentliche Rechenlogik steckt rein und testbar in
 * `splitMath.ts`). Beim Speichern liest das Formular über `getResult()` die
 * fertige Aufteilung, deren Summe dank 1-Cent-Verteilung exakt dem Betrag
 * entspricht.
 */
function AdvancedSplitter({
  participants,
  amount,
  currency,
  payerName,
  initialSplits,
  ref,
}: AdvancedSplitterProps) {
  const hasInitial = !!initialSplits && Object.keys(initialSplits).length > 0;

  const [mode, setMode] = useState<SplitMode>(hasInitial ? "amount" : "percent");
  const [entries, setEntries] = useState<SplitEntry[]>(() =>
    hasInitial
      ? entriesFromSplits(initialSplits!, participants)
      : fairEntries(participants, "percent", amount),
  );

  // Stand der Aufteilung nach der letzten Änderung, die NICHT vom Gesamtbetrag
  // kam. Im Betrag-Modus wird bei jedem neuen Gesamtbetrag von hier aus
  // gerechnet, nicht vom zuletzt angezeigten Stand: Beim Tippen läuft der Betrag
  // über Zwischenwerte ("100" → "" → "1" → "11" → "110"), und über die
  // gerundeten Zwischenstände ginge das Verhältnis (70/30) verloren.
  const [basis, setBasis] = useState(entries);

  function commitEntries(next: SplitEntry[]) {
    setEntries(next);
    setBasis(next);
  }

  // Reagiert (in der Render-Phase, ohne Effekt) auf geänderte Teilnehmer bzw. –
  // im Betrag-Modus – einen geänderten Gesamtbetrag und balanciert neu aus.
  // JSON.stringify als Signatur: robust gegen Namen mit Sonderzeichen (keine
  // Trennzeichen-Kollisionen).
  const participantsSig = JSON.stringify(participants);
  const [reconcile, setReconcile] = useState({ sig: participantsSig, amount });
  if (reconcile.sig !== participantsSig) {
    commitEntries(syncEntries(entries, participants, mode, amount));
    setReconcile({ sig: participantsSig, amount });
  } else if (mode === "amount" && reconcile.amount !== amount) {
    // Leeres/ungültiges Betragsfeld (0): Anzeige stehen lassen statt alles auf
    // 0 zu setzen.
    if (amount > 0) setEntries(redistributeUnlocked(basis, mode, amount));
    setReconcile({ sig: participantsSig, amount });
  }

  // Pro-Person-Beträge (Vorschau + Ergebnis) – Summe stets exakt = amount.
  const previews = useMemo(() => resolveAmounts(entries, amount), [entries, amount]);

  useImperativeHandle(
    ref,
    () => ({
      getResult: () => {
        const splits = resolveSplits(entries, amount);
        return { splits, splitRatio: deriveSplitRatio(splits, payerName, amount) };
      },
    }),
    [entries, amount, payerName],
  );

  function handleModeChange(next: SplitMode) {
    commitEntries(convertMode(entries, mode, next, amount));
    setMode(next);
  }

  // Nutzer setzt einen Wert manuell → Person locken (außer im Anteile-Modus) und
  // den Rest neu auf die Ungelockten verteilen.
  function applyEdit(index: number, value: number) {
    const next = entries.map((entry, i) =>
      i === index
        ? { ...entry, value, locked: mode === "shares" ? entry.locked : true }
        : entry,
    );
    commitEntries(
      mode === "shares" ? next : redistributeUnlocked(next, mode, amount),
    );
  }

  // Fixieren lässt die Übrigen in ihrem Verhältnis. Freigeben heißt "wieder
  // automatisch fair": dann teilen sich alle Ungelockten den Rest gleichmäßig.
  function toggleLock(index: number) {
    const unlocking = entries[index].locked;
    const next = entries.map((entry, i) =>
      i === index ? { ...entry, locked: !entry.locked } : entry,
    );
    commitEntries(
      redistributeUnlocked(next, mode, amount, unlocking ? "even" : "keep-ratio"),
    );
  }

  // Live-Statuszeile: Summe der Eingabewerte vs. Soll (100 % bzw. Betrag).
  const valueSum = sumValues(entries);
  const target = mode === "percent" ? 100 : Math.round(amount * 100) / 100;
  const sumOff =
    mode !== "shares" && Math.abs(valueSum - target) > 0.01;

  return (
    <div className="rounded-xl bg-gray-50 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <label
          htmlFor="split-mode"
          className="text-sm font-medium text-gray-700"
        >
          Aufteilung
        </label>
        <select
          id="split-mode"
          value={mode}
          onChange={(event) => handleModeChange(event.target.value as SplitMode)}
          className="rounded-lg border border-gray-300 bg-white px-2 py-1.5 text-sm font-medium text-gray-700 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30"
        >
          {(Object.keys(MODE_LABELS) as SplitMode[]).map((key) => (
            <option key={key} value={key}>
              {MODE_LABELS[key]}
            </option>
          ))}
        </select>
      </div>

      {participants.length === 0 ? (
        <p className="text-sm text-gray-500">
          Bitte zuerst oben einen Zahler angeben – dann erscheinen hier die
          Teilnehmer.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {entries.map((entry, index) => (
            <SplitRow
              key={entry.name}
              entry={entry}
              mode={mode}
              amount={amount}
              currency={currency}
              preview={previews[index] ?? 0}
              isPayer={entry.name === payerName.trim()}
              onCommit={(value) => applyEdit(index, value)}
              onToggleLock={() => toggleLock(index)}
            />
          ))}
        </ul>
      )}

      {participants.length > 0 && (
        <div className="mt-3 flex items-center justify-between text-xs">
          <span className="text-gray-400">
            Tipp: Ein Wert, den du änderst, bleibt fix – die anderen teilen
            sich den Rest.
          </span>
          {mode !== "shares" && (
            <span
              className={sumOff ? "font-semibold text-red-600" : "text-gray-500"}
            >
              Summe:{" "}
              {mode === "percent"
                ? `${formatValue(valueSum, mode)} %`
                : formatMoney(valueSum, currency)}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

interface SplitRowProps {
  entry: SplitEntry;
  mode: SplitMode;
  amount: number;
  currency: string;
  preview: number;
  isPayer: boolean;
  onCommit: (value: number) => void;
  onToggleLock: () => void;
}

/**
 * Eine Teilnehmer-Zeile: Name, Eingabefeld (mit Einheit), errechneter Betrag und
 * – außer im Anteile-Modus – ein Lock-Schalter. Das Eingabefeld puffert den Text
 * lokal und korrigiert erst beim Verlassen (onBlur/Enter) auf einen gültigen,
 * gerundeten Wert (Float-Support mit 2 Nachkommastellen).
 */
function SplitRow({
  entry,
  mode,
  amount,
  currency,
  preview,
  isPayer,
  onCommit,
  onToggleLock,
}: SplitRowProps) {
  const [text, setText] = useState(() => formatValue(entry.value, mode));

  // Externe Änderungen (Umverteilung, Modus-Wechsel) in die Anzeige spiegeln –
  // ohne Effekt, per Render-Phasen-Vergleich.
  const [sync, setSync] = useState({ value: entry.value, mode });
  if (sync.value !== entry.value || sync.mode !== mode) {
    setSync({ value: entry.value, mode });
    setText(formatValue(entry.value, mode));
  }

  function commit() {
    const parsed = parseAmount(text);
    const clamped = clampValue(Number.isNaN(parsed) ? 0 : parsed, mode, amount);
    setText(formatValue(clamped, mode));
    onCommit(clamped);
  }

  const locked = mode !== "shares" && entry.locked;

  return (
    // Schmale Screens: Name in eigener Zeile über den Eingaben. In einer Zeile
    // bliebe neben Feld, Einheit, Betrag und Schloss kein Platz für den Namen.
    <li className="flex flex-wrap items-center gap-x-2 gap-y-1 sm:flex-nowrap">
      <span className="flex w-full min-w-0 items-center gap-1.5 text-sm text-gray-700 sm:w-auto sm:flex-1">
        <span className="truncate">{entry.name}</span>
        {isPayer && (
          <span className="shrink-0 rounded-full bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
            zahlt
          </span>
        )}
      </span>

      <div className="flex shrink-0 items-center gap-1">
        <input
          type="text"
          inputMode="decimal"
          value={text}
          onFocus={(event) => event.target.select()}
          onChange={(event) => setText(event.target.value)}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              event.currentTarget.blur();
            }
          }}
          aria-label={`Anteil ${entry.name}`}
          className={`w-16 rounded-lg border px-2 py-1.5 text-right font-semibold outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30 ${
            locked
              ? "border-emerald-300 bg-white text-emerald-700"
              : "border-gray-300 bg-white text-gray-700"
          }`}
        />
        <span className="w-14 shrink-0 text-xs font-medium text-gray-400">
          {unitLabel(mode, currency)}
        </span>
      </div>

      <span className="flex-1 text-right text-xs text-gray-500 sm:w-24 sm:flex-none">
        {formatMoney(preview, currency)}
      </span>

      {mode !== "shares" ? (
        <button
          type="button"
          onClick={onToggleLock}
          aria-label={locked ? "Wert freigeben" : "Wert fixieren"}
          title={locked ? "Fixiert – klicken zum Freigeben" : "Klicken zum Fixieren"}
          className={`shrink-0 rounded-lg p-1.5 transition ${
            locked
              ? "text-emerald-600 hover:bg-emerald-100"
              : "text-gray-300 hover:bg-gray-200 hover:text-gray-500"
          }`}
        >
          {locked ? <Lock className="h-4 w-4" /> : <Unlock className="h-4 w-4" />}
        </button>
      ) : (
        <span className="w-7 shrink-0" />
      )}
    </li>
  );
}

export default AdvancedSplitter;
