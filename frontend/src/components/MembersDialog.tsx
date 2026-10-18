import { useState } from "react";
import { Loader2 } from "lucide-react";
import type { MembersValue } from "../api";
import Modal from "./Modal";
import MembersEditor from "./MembersEditor";

interface MembersDialogProps {
  initial: MembersValue;
  onSave: (value: MembersValue) => Promise<void>;
  onClose: () => void;
}

/** Personen einer bestehenden Liste nachträglich ändern (Kopf der Liste). */
function MembersDialog({ initial, onSave, onClose }: MembersDialogProps) {
  const [members, setMembers] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await onSave(members);
      onClose();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Speichern fehlgeschlagen.",
      );
      setSaving(false);
    }
  }

  return (
    <Modal title="Personen der Liste" onClose={onClose}>
      <p className="mb-3 text-sm text-gray-500">
        Neue Ausgaben werden auf diese Personen aufgeteilt. Bestehende Ausgaben
        bleiben, wie sie sind.
      </p>
      <MembersEditor value={members} onChange={setMembers} autoFocus />
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <button
          type="button"
          onClick={onClose}
          disabled={saving}
          className="rounded-xl border border-gray-300 px-4 py-3 font-semibold text-gray-700 transition hover:bg-gray-50 disabled:opacity-50"
        >
          Abbrechen
        </button>
        <button
          type="button"
          onClick={() => void save()}
          disabled={saving}
          className="flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 font-semibold text-white transition hover:bg-emerald-700 disabled:opacity-50"
        >
          {saving ? <Loader2 className="h-5 w-5 animate-spin" /> : "Speichern"}
        </button>
      </div>
    </Modal>
  );
}

export default MembersDialog;
