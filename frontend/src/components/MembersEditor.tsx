import { useState } from "react";
import { House, Plus, UserPlus, X } from "lucide-react";
import type { MembersValue } from "../api";
import { addHaUser, addName, removeMember, unlinkedUsers } from "../haMembers";
import { useHaUsers, useMe } from "../haSession";

interface MembersEditorProps {
  value: MembersValue;
  onChange: (value: MembersValue) => void;
  autoFocus?: boolean;
}

/**
 * Personen einer Liste festlegen: Namen eintippen (Feld + „Hinzufügen“ oder
 * Enter) oder, über Home Assistant geöffnet, HA-Benutzer antippen. Verknüpfte
 * Benutzer sehen die Liste dann auf all ihren Geräten. Darunter die Personen
 * als entfernbare Chips; leere und doppelte Namen werden ignoriert.
 */
function MembersEditor({
  value,
  onChange,
  autoFocus = false,
}: MembersEditorProps) {
  const [draft, setDraft] = useState("");
  const me = useMe();
  const haUsers = useHaUsers(!!me);
  const offered = unlinkedUsers(haUsers.users, value);

  function add() {
    onChange(addName(value, draft));
    setDraft("");
  }

  return (
    <div>
      {me && (offered.length > 0 || haUsers.error) && (
        <div className="mb-3">
          <p className="mb-2 flex items-center gap-1 text-xs font-semibold tracking-wide text-gray-500 uppercase">
            <House className="h-3.5 w-3.5" />
            Aus Home Assistant
          </p>
          {haUsers.error ? (
            <p className="text-sm text-red-600">{haUsers.error}</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {offered.map((user) => (
                <button
                  key={user.id}
                  type="button"
                  onClick={() => onChange(addHaUser(value, user))}
                  className="flex items-center gap-1 rounded-full border border-emerald-600 px-3 py-1.5 text-sm font-medium text-emerald-700 transition hover:bg-emerald-50"
                >
                  <UserPlus className="h-4 w-4" />
                  {user.name}
                  {user.id === me.id && " (du)"}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

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
          placeholder={me ? "Oder Name eintippen, z. B. Max" : "Name, z. B. Max"}
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

      {value.members.length > 0 && (
        <ul
          className="mt-3 flex flex-wrap gap-2"
          aria-label="Personen der Liste"
        >
          {value.members.map((name) => (
            <li
              key={name}
              className="flex items-center gap-1 rounded-full bg-emerald-50 py-1 pr-1 pl-3 text-sm font-medium text-emerald-800"
            >
              {value.memberUsers[name] !== undefined && (
                <House
                  className="h-3.5 w-3.5 text-emerald-600"
                  aria-label="Home-Assistant-Benutzer"
                />
              )}
              {name}
              <button
                type="button"
                onClick={() => onChange(removeMember(value, name))}
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
