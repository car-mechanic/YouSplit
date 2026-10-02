import { useState } from "react";
import { CURRENCIES, MAIN_CURRENCIES } from "../api";

// Sentinel-Wert des Dropdowns: klappt die europäischen Nebenwährungen auf.
const MORE = "__more__";

interface CurrencySelectProps {
  value: string;
  onChange: (code: string) => void;
  id?: string;
  className?: string;
}

const defaultClass =
  "rounded-xl border border-gray-300 bg-white px-2 font-medium text-gray-700 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30";

/**
 * Währungs-Dropdown (Roadmap 3.0 #2): zeigt zunächst nur die kuratierten
 * Hauptwährungen (EUR, USD, CHF, GBP) plus einen Punkt „Mehr…“. Ein Klick darauf
 * klappt alle unterstützten europäischen Währungen auf. Ist bereits eine
 * Nebenwährung gewählt (z. B. beim Bearbeiten), startet das Dropdown direkt
 * aufgeklappt, damit der Wert sichtbar bleibt.
 *
 * In ExpenseForm und EditExpenseModal identisch genutzt (eine Wahrheit).
 */
function CurrencySelect({ value, onChange, id, className }: CurrencySelectProps) {
  const isMain = MAIN_CURRENCIES.some((code) => code === value);
  const [expanded, setExpanded] = useState(!isMain);

  // Auswahlliste: aufgeklappt alle Währungen, sonst nur die Hauptwährungen —
  // ergänzt um den aktuellen Wert, falls er (unerwartet) nicht dabei ist, damit
  // die <select>-value stets zu einer Option passt.
  const options: string[] = expanded ? [...CURRENCIES] : [...MAIN_CURRENCIES];
  if (!options.includes(value)) {
    options.unshift(value);
  }

  function handleChange(next: string) {
    if (next === MORE) {
      setExpanded(true);
      return;
    }
    onChange(next);
  }

  return (
    <select
      id={id}
      value={value}
      onChange={(event) => handleChange(event.target.value)}
      aria-label="Währung"
      className={className ?? defaultClass}
    >
      {options.map((code) => (
        <option key={code} value={code}>
          {code}
        </option>
      ))}
      {!expanded && <option value={MORE}>Mehr…</option>}
    </select>
  );
}

export default CurrencySelect;
