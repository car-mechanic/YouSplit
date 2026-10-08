import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Clock, Loader2, Plus, Receipt, X } from "lucide-react";
import { createList } from "../api";
import { formatDate } from "../format";
import { addRecentList, getRecentLists, removeRecentList } from "../recentLists";
import type { RecentList } from "../recentLists";
import Modal from "../components/Modal";

/**
 * Startseite / Dashboard (Roadmap 3.0 #1).
 *
 * Zwei Aufgaben: eine neue Liste anlegen (CTA → Titel-Modal → Weiterleitung) und
 * die auf diesem Gerät zuletzt besuchten Listen als anklickbare Cards wieder
 * zugänglich machen (aus dem `localStorage`, siehe recentLists.ts). YouSplit hat
 * kein Login – dies ist der Wiedereinstieg in die eigenen Listen.
 */
function Home() {
  const navigate = useNavigate();

  // Zuletzt besuchte Listen einmal beim Mounten aus dem Storage lesen.
  const [recent, setRecent] = useState<RecentList[]>(() => getRecentLists());

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
      // Neue Liste sofort in die Merkliste aufnehmen und öffnen.
      addRecentList(list.id, list.title);
      // Dort startet beim ersten Öffnen das Tutorial (Personen festlegen usw.)
      navigate(`/list/${list.id}`);
    } catch {
      setError("Liste konnte nicht erstellt werden. Läuft das Backend?");
      setCreating(false);
    }
  }

  function handleRemove(id: string) {
    removeRecentList(id);
    setRecent(getRecentLists());
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

      {/* ---------- Zuletzt besucht ---------- */}
      <section className="mt-10">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold tracking-wide text-gray-500 uppercase">
          <Clock className="h-4 w-4" />
          Zuletzt besucht
        </h2>

        {recent.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-200 bg-white p-8 text-center">
            <p className="text-gray-500">
              Noch keine Listen besucht. Erstelle deine erste Liste oder öffne
              einen geteilten Link.
            </p>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {recent.map((item) => (
              <div key={item.id} className="relative">
                <Link
                  to={`/list/${item.id}`}
                  className="block rounded-xl border border-gray-100 bg-white p-4 pr-10 shadow-sm transition hover:border-emerald-200 hover:shadow-md"
                >
                  <p className="truncate font-semibold text-gray-900">
                    {item.title}
                  </p>
                  <p className="mt-1 flex items-center gap-1 text-xs text-gray-400">
                    <Clock className="h-3 w-3" />
                    {formatDate(item.lastVisit)}
                    <ArrowRight className="ml-auto h-4 w-4 text-emerald-600" />
                  </p>
                </Link>
                {/* Aus der Merkliste entfernen (löscht NICHT die Liste selbst) */}
                <button
                  type="button"
                  onClick={() => handleRemove(item.id)}
                  aria-label={`„${item.title}“ aus der Liste entfernen`}
                  className="absolute top-2 right-2 rounded-lg p-1.5 text-gray-300 transition hover:bg-gray-100 hover:text-gray-500"
                >
                  <X className="h-4 w-4" />
                </button>
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
