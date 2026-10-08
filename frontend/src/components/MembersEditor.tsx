import { useState } from "react";
import { Plus, X } from "lucide-react";

interface MembersEditorProps {
  value: string[];
  onChange: (members: string[]) => void;
  autoFocus?: boolean;
}

/**
 * Namen der Personen einer Liste eintippen: Feld + „Hinzufügen“ (oder Enter),
 * darunter die Namen als entfernbare Chips. Leere und doppelte Namen werden
 * ignoriert (das Backend bereinigt zusätzlich).
 */
function MembersEditor({
  value,
  onChange,
  autoFocus = false,
}: MembersEditorProps) {
  const [draft, setDraft] = useState("");

  function add() {
    const name = draft.trim();
    if (name && !value.includes(name)) onChange([...value, name]);
    setDraft("");
  }

  return (
    <div>
      <div className="flex gap-2">
        <input
          type="text"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              add();
            }
          }}
          placeholder="Name, z. B. Max"
          maxLength={100}
          autoFocus={autoFocus}
          aria-label="Name einer Person"
          className="w-full rounded-xl border border-gray-300 px-4 py-3 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30"
        />
        <button
          type="button"
          onClick={add}
          disabled={!draft.trim()}
          className="flex shrink-0 items-center gap-1 rounded-xl bg-emerald-600 px-4 font-semibold text-white transition hover:bg-emerald-700 disabled:opacity-40"
        >
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">Hinzufügen</span>
          <span className="sr-only sm:hidden">Hinzufügen</span>
        </button>
      </div>

      {value.length > 0 && (
        <ul
          className="mt-3 flex flex-wrap gap-2"
          aria-label="Personen der Liste"
        >
          {value.map((name) => (
            <li
              key={name}
              className="flex items-center gap-1 rounded-full bg-emerald-50 py-1 pr-1 pl-3 text-sm font-medium text-emerald-800"
            >
              {name}
              <button
                type="button"
                onClick={() =>
                  onChange(value.filter((member) => member !== name))
                }
                aria-label={`${name} entfernen`}
                className="rounded-full p-1 text-emerald-600 transition hover:bg-emerald-100"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default MembersEditor;
