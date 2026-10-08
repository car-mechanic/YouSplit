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

// Schmale Screens: Icon über dem Text und kleinere Schrift, damit vier Tabs
// nebeneinander passen ("Kontoauszug" ragte sonst aus der Leiste). flex-auto
// gibt langen Wörtern dort mehr Breite als kurzen; min-w-0 erlaubt dem Text,
// notfalls mit … zu kürzen statt überzulaufen.
const TAB_BASE =
  "flex min-w-0 flex-auto flex-col items-center justify-center gap-0.5 rounded-lg px-0.5 py-2 text-[11px] transition sm:flex-1 sm:flex-row sm:gap-1.5 sm:px-2 sm:py-2.5 sm:text-sm";

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
            className={`${TAB_BASE} ${
              isActive
                ? "bg-emerald-600 font-semibold text-white shadow-sm"
                : "font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-700"
            }`}
          >
            <Icon className="h-4 w-4 shrink-0" />
            <span className="max-w-full truncate">{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export default ListTabs;
