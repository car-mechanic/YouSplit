import { useEffect, useRef, useState } from "react";
import { Calendar, ChevronLeft, ChevronRight } from "lucide-react";
import { formatDate } from "../format";

// Wochentage montagsbasiert (deutsche Konvention: Woche beginnt Montag)
const WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const MONTHS = [
  "Januar",
  "Februar",
  "März",
  "April",
  "Mai",
  "Juni",
  "Juli",
  "August",
  "September",
  "Oktober",
  "November",
  "Dezember",
];

// Jahr-Dropdown ab 2020 bis heute + 1 (siehe unten)
const START_YEAR = 2020;

const pad = (value: number) => String(value).padStart(2, "0");
const toIso = (year: number, month: number, day: number) =>
  `${year}-${pad(month + 1)}-${pad(day)}`;

interface DatePickerProps {
  /** Ausgewähltes Datum als ISO "YYYY-MM-DD". */
  value: string;
  onChange: (iso: string) => void;
  id?: string;
}

/**
 * Eigener Datums-Picker im emerald-Card-Design. Ein Klick auf das Feld öffnet
 * darunter einen Monatskalender (Grid) mit Monats-Pfeilen und Jahr-Dropdown.
 * Der Wert wird als ISO "YYYY-MM-DD" gehalten – genau das Format, das das
 * Backend für `receipt_date` erwartet.
 */
function DatePicker({ value, onChange, id }: DatePickerProps) {
  const [open, setOpen] = useState(false);

  // Ausgewählter Wert -> Jahr/Monat/Tag (für Hervorhebung im Grid)
  const [year, month, day] = value.slice(0, 10).split("-").map(Number);

  // Aktuell angezeigter Monat (0-basiert), initial aus dem Wert
  const [viewYear, setViewYear] = useState(year);
  const [viewMonth, setViewMonth] = useState(month - 1);

  // Ändert sich der Wert von außen (z. B. Reset auf heute), springt die
  // Ansicht mit. setState während des Renderns ist Reacts empfohlener Weg
  // (statt eines Effekts), um State auf einen geänderten Prop zu spiegeln.
  const [syncedValue, setSyncedValue] = useState(value);
  if (value !== syncedValue) {
    setSyncedValue(value);
    setViewYear(year);
    setViewMonth(month - 1);
  }

  const containerRef = useRef<HTMLDivElement>(null);

  // Schließen bei Klick außerhalb und bei Escape
  useEffect(() => {
    if (!open) return;
    function handleClick(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  const today = new Date();
  const years: number[] = [];
  for (let y = START_YEAR; y <= today.getFullYear() + 1; y++) years.push(y);

  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  // Wochentag des 1. des Monats, auf Montag=0 umgerechnet
  const firstWeekday = (new Date(viewYear, viewMonth, 1).getDay() + 6) % 7;

  function goMonth(delta: number) {
    let nextMonth = viewMonth + delta;
    let nextYear = viewYear;
    if (nextMonth < 0) {
      nextMonth = 11;
      nextYear -= 1;
    } else if (nextMonth > 11) {
      nextMonth = 0;
      nextYear += 1;
    }
    setViewMonth(nextMonth);
    setViewYear(nextYear);
  }

  function selectDay(selectedDay: number) {
    onChange(toIso(viewYear, viewMonth, selectedDay));
    setOpen(false);
  }

  const isSelected = (d: number) =>
    viewYear === year && viewMonth === month - 1 && d === day;
  const isToday = (d: number) =>
    viewYear === today.getFullYear() &&
    viewMonth === today.getMonth() &&
    d === today.getDate();

  return (
    <div className="relative" ref={containerRef}>
      <button
        id={id}
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center gap-2 rounded-xl border border-gray-300 px-4 py-3 text-left outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30"
      >
        <Calendar className="h-4 w-4 shrink-0 text-emerald-600" />
        <span className="text-gray-900">{formatDate(value)}</span>
      </button>

      {open && (
        <div className="absolute left-0 z-20 mt-2 w-72 rounded-xl border border-gray-100 bg-white p-3 shadow-lg">
          {/* Kopf: Monat blättern + Jahr wählen */}
          <div className="mb-2 flex items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => goMonth(-1)}
              aria-label="Vorheriger Monat"
              className="rounded-lg p-1.5 text-gray-500 transition hover:bg-emerald-50 hover:text-emerald-700"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>

            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-gray-900">
                {MONTHS[viewMonth]}
              </span>
              <select
                value={viewYear}
                onChange={(event) => setViewYear(Number(event.target.value))}
                aria-label="Jahr"
                className="rounded-lg border border-gray-300 bg-white px-2 py-1 text-sm font-medium text-gray-700 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30"
              >
                {years.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </div>

            <button
              type="button"
              onClick={() => goMonth(1)}
              aria-label="Nächster Monat"
              className="rounded-lg p-1.5 text-gray-500 transition hover:bg-emerald-50 hover:text-emerald-700"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          {/* Wochentags-Kopf */}
          <div className="grid grid-cols-7 gap-1 text-center text-xs font-medium text-gray-400">
            {WEEKDAYS.map((weekday) => (
              <span key={weekday} className="py-1">
                {weekday}
              </span>
            ))}
          </div>

          {/* Tage-Grid */}
          <div className="grid grid-cols-7 gap-1">
            {Array.from({ length: firstWeekday }).map((_, index) => (
              <span key={`blank-${index}`} />
            ))}
            {Array.from({ length: daysInMonth }).map((_, index) => {
              const d = index + 1;
              const selected = isSelected(d);
              const todayCell = isToday(d);
              return (
                <button
                  key={d}
                  type="button"
                  onClick={() => selectDay(d)}
                  className={
                    "flex h-9 items-center justify-center rounded-lg text-sm transition " +
                    (selected
                      ? "bg-emerald-600 font-semibold text-white"
                      : todayCell
                        ? "font-semibold text-emerald-700 ring-1 ring-emerald-300 hover:bg-emerald-50"
                        : "text-gray-700 hover:bg-emerald-50")
                  }
                >
                  {d}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default DatePicker;
