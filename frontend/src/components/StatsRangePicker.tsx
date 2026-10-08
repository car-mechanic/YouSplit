import { CalendarRange } from "lucide-react";
import { availableMonths, monthLabel } from "../statsRange";
import type { StatsRange } from "../statsRange";
import type { Expense } from "../api";
import DatePicker from "./DatePicker";

const ALL = "all";
const CUSTOM = "custom";

// Heutiges Datum als ISO "YYYY-MM-DD" (lokale Komponenten, keine Zeitzonen-Drift)
const todayIso = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
};

interface StatsRangePickerProps {
  expenses: readonly Expense[];
  value: StatsRange;
  onChange: (range: StatsRange) => void;
  /** Anzahl Ausgaben im gewählten Zeitraum (Rückmeldung unter der Auswahl). */
  matchCount: number;
}

/**
 * Zeitraum der Statistik wie in einer Banking-App: Schnellauswahl der Monate mit
 * Ausgaben (neueste zuerst) oder ein eigener Zeitraum mit Von/Bis.
 */
function StatsRangePicker({
  expenses,
  value,
  onChange,
  matchCount,
}: StatsRangePickerProps) {
  const months = availableMonths(expenses);
  const selected = value.kind === "month" ? value.month : value.kind;

  function handleSelect(next: string) {
    if (next === ALL) {
      onChange({ kind: "all" });
    } else if (next === CUSTOM) {
      // Start: vom Ersten des neuesten Monats mit Ausgaben bis heute
      const from = months.length > 0 ? `${months[0]}-01` : todayIso();
      onChange({ kind: "custom", from, to: todayIso() });
    } else {
      onChange({ kind: "month", month: next });
    }
  }

  return (
    <section className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
      <label
        htmlFor="stats-range"
        className="mb-1 flex items-center gap-2 text-sm font-medium text-gray-700"
      >
        <CalendarRange className="h-4 w-4 text-emerald-600" />
        Zeitraum
      </label>
      <select
        id="stats-range"
        value={selected}
        onChange={(event) => handleSelect(event.target.value)}
        className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30"
      >
        <option value={ALL}>Gesamter Zeitraum</option>
        {months.map((month) => (
          <option key={month} value={month}>
            {monthLabel(month)}
          </option>
        ))}
        <option value={CUSTOM}>Eigener Zeitraum …</option>
      </select>

      {value.kind === "custom" && (
        <div className="mt-3 grid grid-cols-2 gap-3">
          <div>
            <label
              htmlFor="stats-from"
              className="mb-1 block text-xs font-medium text-gray-500"
            >
              Von
            </label>
            <DatePicker
              id="stats-from"
              value={value.from}
              onChange={(from) => onChange({ ...value, from })}
            />
          </div>
          <div>
            <label
              htmlFor="stats-to"
              className="mb-1 block text-xs font-medium text-gray-500"
            >
              Bis
            </label>
            <DatePicker
              id="stats-to"
              value={value.to}
              onChange={(to) => onChange({ ...value, to })}
            />
          </div>
        </div>
      )}

      <p className="mt-2 text-xs text-gray-400">
        {matchCount === 1 ? "1 Ausgabe" : `${matchCount} Ausgaben`} im Zeitraum
      </p>
    </section>
  );
}

export default StatsRangePicker;
