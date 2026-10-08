import { useRef, useState } from "react";
import { Check, X } from "lucide-react";
import { categoryLabel } from "../categories";

// Sentinel-Wert des Dropdowns für "Eigene Kategorie hinzufügen …"
const NEW_CATEGORY = "__new_category__";

const inputClass =
  "w-full rounded-xl border border-gray-300 px-4 py-3 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30";
const iconButtonClass =
  "shrink-0 rounded-xl border border-gray-300 px-3 text-gray-400 transition hover:bg-gray-50 hover:text-gray-600";

interface CategorySelectProps {
  id: string;
  value: string;
  /** Wählbare Kategorien (Standards + eigene der Liste, siehe categoryOptions). */
  options: string[];
  onChange: (category: string) => void;
}

/**
 * Kategorie-Dropdown mit „Eigene Kategorie hinzufügen …“ am Ende. Eine neue
 * Kategorie wird mit der Ausgabe gespeichert und erscheint danach für alle
 * Personen der Liste im Dropdown (die Optionen ergeben sich aus den Ausgaben).
 */
function CategorySelect({ id, value, options, onChange }: CategorySelectProps) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // Den aktuellen Wert immer anbieten – auch eine gerade erst angelegte oder
  // eine alte Kategorie, die nicht (mehr) in der Liste steht.
  const shown = options.includes(value) ? options : [...options, value];

  function handleSelect(next: string) {
    if (next === NEW_CATEGORY) {
      setDraft("");
      setAdding(true);
      requestAnimationFrame(() => inputRef.current?.focus());
      return;
    }
    onChange(next);
  }

  function confirm() {
    const name = draft.trim();
    if (name) onChange(name);
    setAdding(false);
  }

  if (adding) {
    return (
      <div className="flex gap-2">
        <input
          id={id}
          ref={inputRef}
          type="text"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            // Enter übernimmt die Kategorie, statt das ganze Formular abzuschicken
            if (event.key === "Enter") {
              event.preventDefault();
              confirm();
            } else if (event.key === "Escape") {
              setAdding(false);
            }
          }}
          placeholder="z. B. Urlaubskasse"
          maxLength={100}
          className={inputClass}
        />
        <button
          type="button"
          onClick={confirm}
          disabled={!draft.trim()}
          aria-label="Kategorie übernehmen"
          className={`${iconButtonClass} disabled:opacity-40`}
        >
          <Check className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => setAdding(false)}
          aria-label="Zurück zur Auswahl"
          className={iconButtonClass}
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <select
      id={id}
      value={value}
      onChange={(event) => handleSelect(event.target.value)}
      className={`${inputClass} bg-white`}
    >
      {shown.map((category) => (
        <option key={category} value={category}>
          {categoryLabel(category)}
        </option>
      ))}
      <option value={NEW_CATEGORY}>Eigene Kategorie hinzufügen …</option>
    </select>
  );
}

export default CategorySelect;
