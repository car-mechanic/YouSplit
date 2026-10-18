import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Clock, Loader2, Plus, Receipt, Users, X } from "lucide-react";
import { createList, forgetList, getMyLists, importLists } from "../api";
import type { MyList } from "../api";
import { formatDate } from "../format";
import { useMe } from "../haSession";
import { useLiveRefresh } from "../liveRefresh";
import {
  addRecentList,
  clearRecentLists,
  getRecentLists,
  removeRecentList,
} from "../recentLists";
import type { RecentList } from "../recentLists";
import Modal from "../components/Modal";

// Neue geteilte Listen anderer erscheinen ohne Neuladen
const LIVE_REFRESH_MS = 30_000;

/** Eine Karte der Startseite, egal ob vom Server oder aus dem Browser. */
interface ListCard {
  id: string;
  title: string;
  /** Unterzeile: Datum des letzten Besuchs oder Hinweis */
  subtitle: string;
  /** Darf aus der Übersicht entfernt werden */
  removable: boolean;
  shared: boolean;
}

function fromServer(item: MyList): ListCard {
  return {
    id: item.id,
    title: item.title,
    subtitle: item.last_visit ? formatDate(item.last_visit) : "Mit dir geteilt",
    // Als Person verknüpft: bleibt sichtbar, solange die Verknüpfung besteht
    removable: !item.is_member,
    shared: item.is_member,
  };
}

function fromBrowser(item: RecentList): ListCard {
  return {
    id: item.id,
    title: item.title,
    subtitle: formatDate(item.lastVisit),
    removable: true,
    shared: false,
  };
}

/**
 * Startseite / Dashboard (Roadmap 3.0 #1).
 *
 * Zwei Aufgaben: eine neue Liste anlegen (CTA → Titel-Modal → Weiterleitung) und
 * die eigenen Listen als anklickbare Cards wieder zugänglich machen.
 *
 * Über Home Assistant kommen sie vom Server („Meine Listen“, auf allen Geräten
 * gleich). Ohne Home Assistant (direkter Port) gibt es kein Konto: dann bleibt
 * es bei den in diesem Browser besuchten Listen (recentLists.ts).
 */
function Home() {
  const navigate = useNavigate();
  const me = useMe();

  // Ohne HA-Benutzer: einmal beim Mounten aus dem Storage lesen.
  const [recent, setRecent] = useState<RecentList[]>(() => getRecentLists());
  // Mit HA-Benutzer: null, solange „Meine Listen“ noch lädt
  const [mine, setMine] = useState<MyList[] | null>(null);
  const [listsError, setListsError] = useState<string | null>(null);

  const loadMine = useCallback(() => {
    getMyLists()
      .then((lists) => {
        setMine(lists);
        setListsError(null);
      })
      .catch(() => setListsError("Deine Listen konnten nicht geladen werden."));
  }, []);

  useEffect(() => {
    if (!me) return;
    // Was dieser Browser bisher nur lokal kannte, einmalig übernehmen. Danach
    // ist der Server maßgeblich: entfernte Listen kämen sonst wieder.
    const local = getRecentLists().map((item) => item.id);
    const imported =
      local.length > 0
        ? importLists(local).then(() => clearRecentLists())
        : Promise.resolve();
    imported
      .catch(() => {
        // Übernahme klappt beim nächsten Aufruf erneut
      })
      .finally(loadMine);
  }, [me, loadMine]);

  useLiveRefresh(
    useCallback(() => {
      if (me) loadMine();
    }, [me, loadMine]),
    LIVE_REFRESH_MS,
  );

  // undefined: Benutzer unbekannt, null: Server-Listen laden noch
  const cards: ListCard[] | null =
    me === undefined
      ? null
      : me
        ? (mine?.map(fromServer) ?? null)
        : recent.map(fromBrowser);

  // Anlege-Modal
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function openCreate() {
    setTitle("");
    setError(null);
    setShowCreate(true);
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) return;

    setCreating(true);
    setError(null);
    try {
      const list = await createList(title.trim());
      // Ohne Home Assistant: neue Liste sofort in die Merkliste aufnehmen.
      // Mit Home Assistant merkt sie sich der Server beim Öffnen.
      if (!me) addRecentList(list.id, list.title);
      // Dort startet beim ersten Öffnen das Tutorial (Personen festlegen usw.)
      navigate(`/list/${list.id}`);
    } catch {
      setError("Liste konnte nicht erstellt werden. Läuft das Backend?");
      setCreating(false);
    }
  }

  function handleRemove(id: string) {
    if (!me) {
      removeRecentList(id);
      setRecent(getRecentLists());
      return;
    }
    setMine((prev) => prev?.filter((item) => item.id !== id) ?? prev);
    forgetList(id).catch(() => {
      setListsError("Liste konnte nicht entfernt werden.");
      loadMine();
    });
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-10 sm:py-14">
      {/* ---------- Marke ---------- */}
      <div className="mb-8 flex flex-col items-center text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-600 shadow-lg shadow-emerald-600/30">
          <Receipt className="h-8 w-8 text-white" />
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-gray-900">
          YouSplit
        </h1>
        <p className="mt-2 max-w-md text-gray-500">
          Gemeinsame Ausgaben festhalten – ganz ohne Konto. Liste erstellen, Link
          teilen, fertig.
        </p>
      </div>

      {/* ---------- CTA: Neue Liste ---------- */}
      <button
        type="button"
        onClick={openCreate}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-4 text-lg font-semibold text-white shadow-lg shadow-emerald-600/20 transition hover:bg-emerald-700"
      >
        <Plus className="h-6 w-6" />
        Neue Liste erstellen
      </button>

      {/* ---------- Meine Listen / Zuletzt besucht ---------- */}
      <section className="mt-10">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold tracking-wide text-gray-500 uppercase">
          <Clock className="h-4 w-4" />
          {me ? "Meine Listen" : "Zuletzt besucht"}
        </h2>

        {listsError && <p className="mb-3 text-sm text-red-600">{listsError}</p>}

        {cards === null ? (
          !listsError && (
            <div className="flex justify-center p-8">
              <Loader2 className="h-6 w-6 animate-spin text-emerald-600" />
            </div>
          )
        ) : cards.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-200 bg-white p-8 text-center">
            <p className="text-gray-500">
              Noch keine Listen. Erstelle deine erste Liste oder öffne einen
              geteilten Link.
            </p>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {cards.map((item) => (
              <div key={item.id} className="relative">
                <Link
                  to={`/list/${item.id}`}
                  className="block rounded-xl border border-gray-100 bg-white p-4 pr-10 shadow-sm transition hover:border-emerald-200 hover:shadow-md"
                >
                  <p className="truncate font-semibold text-gray-900">
                    {item.title}
                  </p>
                  <p className="mt-1 flex items-center gap-1 text-xs text-gray-400">
                    {item.shared ? (
                      <Users className="h-3 w-3" aria-label="Du bist Person der Liste" />
                    ) : (
                      <Clock className="h-3 w-3" />
                    )}
                    {item.subtitle}
                    <ArrowRight className="ml-auto h-4 w-4 text-emerald-600" />
                  </p>
                </Link>
                {/* Aus der Übersicht entfernen (löscht NICHT die Liste selbst) */}
                {item.removable && (
                  <button
                    type="button"
                    onClick={() => handleRemove(item.id)}
                    aria-label={`„${item.title}“ aus der Übersicht entfernen`}
                    className="absolute top-2 right-2 rounded-lg p-1.5 text-gray-300 transition hover:bg-gray-100 hover:text-gray-500"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ---------- Modal: Titel für neue Liste ---------- */}
      {showCreate && (
        <Modal title="Neue Liste erstellen" onClose={() => setShowCreate(false)}>
          <form onSubmit={handleCreate}>
            <label
              htmlFor="new-list-title"
              className="mb-2 block text-sm font-medium text-gray-700"
            >
              Wofür ist die Liste?
            </label>
            <input
              id="new-list-title"
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="z. B. Urlaub Italien"
              maxLength={200}
              autoFocus
              className="w-full rounded-xl border border-gray-300 px-4 py-3 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30"
            />

            {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

            <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                disabled={creating}
                className="rounded-xl border border-gray-300 px-4 py-3 font-semibold text-gray-700 transition hover:bg-gray-50 disabled:opacity-50"
              >
                Abbrechen
              </button>
              <button
                type="submit"
                disabled={creating || !title.trim()}
                className="flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {creating ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <>
                    Erstellen
                    <ArrowRight className="h-5 w-5" />
                  </>
                )}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </main>
  );
}

export default Home;
