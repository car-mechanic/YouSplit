import { useMemo, useState } from "react";
import { BarChart3, PieChart as PieChartIcon } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Expense } from "../api";
import { categoryLabel } from "../categories";
import { formatEuro } from "../format";
import { filterByRange } from "../statsRange";
import type { StatsRange } from "../statsRange";
import StatsRangePicker from "./StatsRangePicker";

// Emerald/Teal/Cyan-Palette: die Kategorien im Donut bekommen der Reihe nach
// (nach Betrag absteigend) eine Farbe. Bewusst nur "kühle Grün-Blau-Töne", damit
// es zum Finanz-Grün der App passt und harmonisch bleibt.
const CATEGORY_COLORS = [
  "#059669", // emerald-600
  "#0d9488", // teal-600
  "#0891b2", // cyan-600
  "#34d399", // emerald-400
  "#2dd4bf", // teal-400
  "#22d3ee", // cyan-400
  "#047857", // emerald-700
  "#0f766e", // teal-700
];

// Balken (Ausgaben je Person) einheitlich im Finanz-Grün – die Farbe trägt hier
// keine Bedeutung (anders als beim Kategorie-Donut), es ist überall "Geld".
const BAR_COLOR = "#059669";

interface ChartDatum {
  name: string;
  value: number;
}

interface StatisticsBoardProps {
  expenses: Expense[];
}

/** Prozentwert deutsch formatieren (max. 1 Nachkommastelle), z. B. "45,3 %". */
function formatPercent(value: number): string {
  return `${value.toLocaleString("de-DE", { maximumFractionDigits: 1 })} %`;
}

/**
 * Visuelle Auswertung der Ausgaben (Roadmap 2.0 #2). Zwei Diagramme:
 *  1. Donut – Verteilung der Ausgaben nach Kategorie (prozentual).
 *  2. Balken – Summe der getätigten Ausgaben je Person.
 *
 * Die Aggregation läuft performant direkt hier im Frontend (die Ausgaben liegen
 * ohnehin im State) und wird via useMemo nur bei Änderung der Liste neu berechnet.
 * Reine Darstellung – kein eigener Fach-State.
 */
function StatisticsBoard({ expenses }: StatisticsBoardProps) {
  // Gewählter Zeitraum (Standard: alles). Lebt nur hier – reine Ansichtssache.
  const [range, setRange] = useState<StatsRange>({ kind: "all" });
  const inRange = useMemo(
    () => filterByRange(expenses, range),
    [expenses, range],
  );

  const { byCategory, byPerson, total } = useMemo(() => {
    const categorySums = new Map<string, number>();
    const personSums = new Map<string, number>();
    let sum = 0;

    for (const expense of inRange) {
      // Immer in EUR (Basiswährung) aggregieren: Fremdwährungen über den
      // gespeicherten Tageskurs umrechnen (amount * exchange_rate).
      const eur = expense.amount * expense.exchange_rate;
      // Leere Kategorie und Altwert "Unknown/Manuell" als "Ohne Kategorie"
      const category = categoryLabel(expense.category);
      categorySums.set(category, (categorySums.get(category) ?? 0) + eur);
      personSums.set(
        expense.payer_name,
        (personSums.get(expense.payer_name) ?? 0) + eur,
      );
      sum += eur;
    }

    // Nach Betrag absteigend – so bekommt die größte Kategorie die erste Farbe
    const toSortedData = (map: Map<string, number>): ChartDatum[] =>
      [...map.entries()]
        .map(([name, value]) => ({ name, value }))
        .sort((a, b) => b.value - a.value);

    return {
      byCategory: toSortedData(categorySums),
      byPerson: toSortedData(personSums),
      total: sum,
    };
  }, [inRange]);

  // ---------- Empty State ----------
  if (expenses.length === 0) {
    return (
      <section className="mt-4 rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
        <div className="flex flex-col items-center gap-4 px-6 py-12 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50">
            <BarChart3 className="h-7 w-7 text-emerald-600" />
          </div>
          <div>
            <p className="font-semibold text-gray-900">
              Noch keine Statistiken
            </p>
            <p className="mt-1 text-sm text-gray-500">
              Füge Ausgaben hinzu, um Statistiken zu sehen – wir werten sie
              automatisch nach Kategorie und Person aus.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <div className="mt-4 space-y-4">
      <StatsRangePicker
        expenses={expenses}
        value={range}
        onChange={setRange}
        matchCount={inRange.length}
      />

      {inRange.length === 0 ? (
        <section className="rounded-xl border border-gray-100 bg-white px-6 py-10 text-center shadow-sm">
          <p className="font-semibold text-gray-900">
            Keine Ausgaben in diesem Zeitraum
          </p>
          <p className="mt-1 text-sm text-gray-500">
            Wähle einen anderen Monat oder einen größeren Zeitraum.
          </p>
        </section>
      ) : (
        <>
          {/* ---------- Chart 1: Ausgaben nach Kategorie (Donut) ---------- */}
          <section className="rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
            <h2 className="flex items-center gap-2 text-base font-semibold text-gray-900">
              <PieChartIcon className="h-5 w-5 text-emerald-600" />
              Ausgaben nach Kategorie
            </h2>

            {/* Donut mit zentrierter Gesamtsumme in der Mitte */}
            <div className="relative mt-4">
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={byCategory}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={62}
                    outerRadius={92}
                    paddingAngle={byCategory.length > 1 ? 2 : 0}
                    strokeWidth={0}
                  >
                    {byCategory.map((entry, index) => (
                      <Cell
                        key={entry.name}
                        fill={CATEGORY_COLORS[index % CATEGORY_COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value) => formatEuro(Number(value))}
                    contentStyle={{
                      borderRadius: "0.75rem",
                      border: "1px solid #f3f4f6",
                      fontSize: "0.875rem",
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              {/* Mittelbeschriftung: Gesamtsumme (rein visuell, ignoriert Klicks) */}
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-xs uppercase tracking-wide text-gray-400">
                  Gesamt
                </span>
                <span className="text-xl font-bold text-gray-900">
                  {formatEuro(total)}
                </span>
              </div>
            </div>

            {/* Eigene Legende mit Betrag + Prozentanteil (mobil besser lesbar als
            Beschriftungen direkt im Ring) */}
            <ul className="mt-4 space-y-2">
              {byCategory.map((entry, index) => (
                <li
                  key={entry.name}
                  className="flex items-center justify-between gap-3 text-sm"
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <span
                      className="h-3 w-3 shrink-0 rounded-full"
                      style={{
                        backgroundColor:
                          CATEGORY_COLORS[index % CATEGORY_COLORS.length],
                      }}
                    />
                    <span className="truncate text-gray-700">{entry.name}</span>
                  </span>
                  <span className="flex shrink-0 items-center gap-2">
                    <span className="font-semibold text-gray-900">
                      {formatEuro(entry.value)}
                    </span>
                    <span className="w-14 text-right text-gray-400">
                      {formatPercent((entry.value / total) * 100)}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </section>

          {/* ---------- Chart 2: Wer hat wie viel bezahlt? (Balken) ---------- */}
          <section className="rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
            <h2 className="flex items-center gap-2 text-base font-semibold text-gray-900">
              <BarChart3 className="h-5 w-5 text-emerald-600" />
              Wer hat wie viel bezahlt?
            </h2>

            <div className="mt-4">
              <ResponsiveContainer width="100%" height={240}>
                <BarChart
                  data={byPerson}
                  margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                    stroke="#f3f4f6"
                  />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 12, fill: "#6b7280" }}
                    tickLine={false}
                    axisLine={{ stroke: "#e5e7eb" }}
                    interval={0}
                  />
                  <YAxis
                    width={48}
                    tick={{ fontSize: 12, fill: "#9ca3af" }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => `${value} €`}
                  />
                  <Tooltip
                    cursor={{ fill: "#ecfdf5" }}
                    formatter={(value) => formatEuro(Number(value))}
                    contentStyle={{
                      borderRadius: "0.75rem",
                      border: "1px solid #f3f4f6",
                      fontSize: "0.875rem",
                    }}
                  />
                  <Bar dataKey="value" fill={BAR_COLOR} radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

export default StatisticsBoard;
