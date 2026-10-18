import { useState } from "react";
import type { ReactNode } from "react";
import { Check, Link2, Loader2 } from "lucide-react";
import type { MembersValue } from "../api";
import { linkedName, linkSelf, sameMembers } from "../haMembers";
import { useMe } from "../haSession";
import { payerStorageKey } from "../payerStorage";
import { copyCurrentLink } from "../clipboard";
import MembersEditor from "./MembersEditor";
import Modal from "./Modal";

interface ListTutorialProps {
  listId: string;
  initialMembers: MembersValue;
  /** Speichert die Personen im Backend; wirft bei Fehlern. */
  onSaveMembers: (value: MembersValue) => Promise<void>;
  onClose: () => void;
}

type Step = "members" | "me" | "expenses" | "settlement" | "share";

/**
 * Kurzes Tutorial direkt nach dem Anlegen einer Liste (2026-10-08).
 *
 * Wichtigster Schritt ist der erste: die Personen der Liste. Ohne sie würde die
 * erste Ausgabe zu 100 % beim Zahler landen, die zweite 50/50 – und frühere
 * Ausgaben müsste man von Hand nachteilen. Danach: wer man selbst ist (wird auf
 * diesem Gerät als Zahler vorgeschlagen, über Home Assistant mit dem eigenen
 * Konto verknüpft) und drei kurze Hinweise.
 */
function ListTutorial({
  listId,
  initialMembers,
  onSaveMembers,
  onClose,
}: ListTutorialProps) {
  const user = useMe();
  const [members, setMembers] = useState(initialMembers);
  // Zuletzt gespeicherter Stand: nur bei Änderungen erneut speichern
  const [saved, setSaved] = useState(initialMembers);
  const [me, setMe] = useState<string | null>(null);
  const [step, setStep] = useState<Step>("members");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // "Wer bist du?" nur, wenn es Personen zur Auswahl gibt
  const steps: Step[] =
    members.members.length > 0
      ? ["members", "me", "expenses", "settlement", "share"]
      : ["members", "expenses", "settlement", "share"];
  const index = steps.indexOf(step);
  const isLast = index === steps.length - 1;
  const myName = me ?? linkedName(members.memberUsers, user?.id);

  /** Speichert `value`, falls geändert. false bei Fehler (Meldung steht dann). */
  async function persist(value: MembersValue): Promise<boolean> {
    // Wer über einen Link dazukommt, übernimmt meist nur die schon
    // eingetragenen Namen: dann gibt es nichts zu speichern.
    if (sameMembers(value, saved)) return true;
    setSaving(true);
    setError(null);
    try {
      await onSaveMembers(value);
      setSaved(value);
      return true;
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Speichern fehlgeschlagen.",
      );
      return false;
    } finally {
      setSaving(false);
    }
  }

  function pickMe(name: string) {
    setMe(name);
    // Über Home Assistant: die Person gleich mit dem eigenen Konto verknüpfen
    if (user) setMembers((value) => linkSelf(value, name, user.id));
  }

  async function next() {
    if ((step === "members" || step === "me") && !(await persist(members))) {
      return;
    }
    if (step === "me" && myName) {
      try {
        localStorage.setItem(payerStorageKey(listId), myName);
      } catch {
        // Speicher nicht verfügbar (privater Modus): nur kein Vorschlag
      }
    }
    if (isLast) onClose();
    else setStep(steps[index + 1]);
  }

  async function copyLink() {
    if (await copyCurrentLink()) setCopied(true);
  }

  const content: Record<Step, { title: string; body: ReactNode }> = {
    members: {
      title: "Wer ist dabei?",
      body: (
        <>
          <p className="mb-3 text-sm text-gray-600">
            {initialMembers.members.length > 0
              ? "Diese Personen sind schon in der Liste. Fehlt jemand? Dann trag ihn hier ein."
              : "Trag alle Personen ein, die sich die Kosten teilen. Dann wird schon die erste Ausgabe auf alle aufgeteilt."}
            {user &&
              " Home-Assistant-Benutzer sehen die Liste dann automatisch auf all ihren Geräten."}
          </p>
          <MembersEditor value={members} onChange={setMembers} autoFocus />
        </>
      ),
    },
    me: {
      title: "Wer bist du?",
      body: (
        <>
          <p className="mb-3 text-sm text-gray-600">
            {user
              ? "Tipp auf deinen Namen. Er wird mit deinem Home-Assistant-Konto verknüpft: Du siehst die Liste auf all deinen Geräten und wirst als Zahler vorgeschlagen."
              : "Tipp auf deinen Namen. Auf diesem Gerät schlagen wir dich dann als Zahler vor."}{" "}
            Nicht dabei? Geh zurück und trag dich ein.
          </p>
          <div className="flex flex-wrap gap-2">
            {members.members.map((name) => {
              const owner = members.memberUsers[name];
              // Mit einem anderen HA-Benutzer verknüpft: das ist jemand anderes
              const taken = !!user && owner !== undefined && owner !== user.id;
              return (
                <button
                  key={name}
                  type="button"
                  onClick={() => pickMe(name)}
                  disabled={taken}
                  aria-pressed={myName === name}
                  className={`flex items-center gap-1 rounded-full border px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${
                    myName === name
                      ? "border-emerald-600 bg-emerald-600 text-white"
                      : "border-gray-300 text-gray-700 hover:bg-gray-50"
                  }`}
                >
                  {myName === name && <Check className="h-4 w-4" />}
                  {name}
                </button>
              );
            })}
          </div>
        </>
      ),
    },
    expenses: {
      title: "Ausgaben eintragen",
      body: (
        <ul className="list-disc space-y-2 pl-5 text-sm text-gray-600">
          <li>Titel und Betrag eingeben – die Kategorie wird vorgeschlagen.</li>
          <li>
            Jede Ausgabe wird gleichmäßig auf alle geteilt. Bei „Aufteilung“
            kannst du das für eine einzelne Ausgabe ändern, z. B. 70/30.
          </li>
        </ul>
      ),
    },
    settlement: {
      title: "Wer schuldet wem?",
      body: (
        <ul className="list-disc space-y-2 pl-5 text-sm text-gray-600">
          <li>„Kassensturz“ zeigt, wer wem wie viel schuldet.</li>
          <li>
            „Statistiken“ zeigt die Ausgaben nach Kategorie und Person, auch für
            einzelne Monate.
          </li>
        </ul>
      ),
    },
    share: {
      title: "Liste teilen",
      body: (
        <>
          <p className="text-sm text-gray-600">
            Schick den Link an die anderen. Wer ihn hat, kann mitmachen – ganz
            ohne Konto.
          </p>
          <button
            type="button"
            onClick={copyLink}
            className="mt-4 flex items-center gap-2 rounded-xl border border-emerald-600 px-4 py-2.5 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-50"
          >
            {copied ? (
              <Check className="h-4 w-4" />
            ) : (
              <Link2 className="h-4 w-4" />
            )}
            {copied ? "Link kopiert" : "Link kopieren"}
          </button>
        </>
      ),
    },
  };

  return (
    <Modal title={content[step].title} onClose={onClose}>
      <div className="min-h-32">{content[step].body}</div>
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {/* Fortschritt als Punkte */}
      <div
        className="mt-6 flex justify-center gap-1.5"
        aria-label={`Schritt ${index + 1} von ${steps.length}`}
      >
        {steps.map((name, i) => (
          <span
            key={name}
            className={`h-1.5 rounded-full transition-all ${
              i === index ? "w-5 bg-emerald-600" : "w-1.5 bg-gray-300"
            }`}
          />
        ))}
      </div>

      <div className="mt-5 flex items-center justify-between gap-2">
        {index === 0 ? (
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl px-3 py-3 text-sm font-medium text-gray-500 transition hover:bg-gray-50"
          >
            Überspringen
          </button>
        ) : (
          <button
            type="button"
            onClick={() => setStep(steps[index - 1])}
            disabled={saving}
            className="rounded-xl border border-gray-300 px-4 py-3 font-semibold text-gray-700 transition hover:bg-gray-50"
          >
            Zurück
          </button>
        )}
        <button
          type="button"
          onClick={() => void next()}
          disabled={saving}
          className="flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-5 py-3 font-semibold text-white transition hover:bg-emerald-700 disabled:opacity-50"
        >
          {saving && <Loader2 className="h-5 w-5 animate-spin" />}
          {isLast ? "Los geht’s" : "Weiter"}
        </button>
      </div>
    </Modal>
  );
}

export default ListTutorial;
