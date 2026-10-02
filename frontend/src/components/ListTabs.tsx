import type { ComponentType } from "react";
import { BarChart3, Landmark, Receipt, Users } from "lucide-react";

// Die Ansichten der Detailseite. Der Wert wird in ListView als State gehalten
// und steuert, welcher Block gerendert wird.
export type ListTab =
  | "expenses"
  | "settlement"
  | "statistics"
  | "bankstatement";

// Icon nur über die genutzte Prop (className) typisieren – unabhängig davon,
// wie lucide-react seinen Icon-Typ exportiert.
type TabDef = {
  id: ListTab;
  label: string;
  icon: ComponentType<{ className?: string }>;
};

const TABS: TabDef[] = [
  { id: "expenses", label: "Ausgaben", icon: Receipt },
  { id: "settlement", label: "Kassensturz", icon: Users },
  { id: "statistics", label: "Statistiken", icon: BarChart3 },
  { id: "bankstatement", label: "Kontoauszug", icon: Landmark },
];

interface ListTabsProps {
  active: ListTab;
  onChange: (tab: ListTab) => void;
}

/**
 * Mobile-freundliche Tab-Leiste (Segmented Control) über dem Inhalt der
 * Detailseite. Rein darstellend: hält keinen eigenen State, meldet die Auswahl
 * nur über onChange nach oben (ListView entscheidet, was gezeigt wird).
 */
function ListTabs({ active, onChange }: ListTabsProps) {
  return (
    <div
      role="tablist"
      aria-label="Ansicht wählen"
      className="mt-6 flex gap-1 rounded-xl border border-gray-100 bg-white p-1 shadow-sm"
    >
      {TABS.map((tab) => {
        const Icon = tab.icon;
        const isActive = tab.id === active;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.id)}
            className={
              isActive
                ? "flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-2 py-2.5 text-sm font-semibold text-white shadow-sm transition"
                : "flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-2.5 text-sm font-medium text-gray-500 transition hover:bg-gray-50 hover:text-gray-700"
            }
          >
            <Icon className="h-4 w-4 shrink-0" />
            <span className="truncate">{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export default ListTabs;
