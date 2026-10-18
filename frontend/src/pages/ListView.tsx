import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Loader2 } from "lucide-react";
import {
  deleteExpense,
  getList,
  getSettlement,
  recordVisit,
  setMembers,
  updateExpense,
  withReason,
} from "../api";
import type {
  CurrentUser,
  Expense,
  ExpenseUpdate,
  MembersValue,
  SharedList,
  Settlement,
} from "../api";
import ConfirmDialog from "../components/ConfirmDialog";
import EditExpenseModal from "../components/EditExpenseModal";
import ExpenseForm from "../components/ExpenseForm";
import ExpenseList from "../components/ExpenseList";
import BankStatementView from "../components/BankStatementView";
import ListHeader from "../components/ListHeader";
import ListTutorial from "../components/ListTutorial";
import MembersDialog from "../components/MembersDialog";
import ListTabs from "../components/ListTabs";
import type { ListTab } from "../components/ListTabs";
import SettlementCard from "../components/SettlementCard";
import StatisticsBoard from "../components/StatisticsBoard";
import { formatMoney } from "../format";
import { categoryOptions } from "../categories";
import { linkedName } from "../haMembers";
import { loadMe } from "../haSession";
import { useLiveRefresh } from "../liveRefresh";
import { collectParticipants } from "../participants";
import { addRecentList } from "../recentLists";
import { markTutorialDone, shouldShowTutorial } from "../tutorialStorage";

/**
 * Detailseite einer geteilten Liste (Route /list/:id).
 *
 * Orchestriert das Laden der Liste, den vom Backend berechneten Kassensturz
 * (Settlement) sowie das Bearbeiten/Löschen einzelner Ausgaben. Die eigentliche
 * Darstellung liegt in fokussierten Teil-Komponenten: ListHeader (Kopf),
 * SettlementCard (Kassensturz), ExpenseForm (Anlegen/Scannen) und ExpenseList.
 *
 * Änderungen anderer Geräte holt die Seite alle LIVE_REFRESH_MS nach.
 */
const LIVE_REFRESH_MS = 10_000;

function ListView() {
  const { id } = useParams<{ id: string }>();

  // Tutorial beim ersten Öffnen der Liste auf diesem Gerät – nach dem Anlegen
  // wie über einen geteilten Link (siehe tutorialStorage.ts). Entschieden wird
  // erst nach dem Laden: wer als HA-Benutzer schon verknüpft ist, kennt die
  // Liste von einem anderen Gerät.
  const [showTutorial, setShowTutorial] = useState(false);
  const [editingMembers, setEditingMembers] = useState(false);
  // Neu einhängen des Formulars nach dem Tutorial: es liest den dort gewählten
  // Zahler ("Wer bist du?") nur beim Einhängen aus dem localStorage.
  const [formKey, setFormKey] = useState(0);

  const [list, setList] = useState<SharedList | null>(null);
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Zählt eigene Änderungen. Ein Nachladen, das vor einer eigenen Änderung
  // gestartet ist, kennt sie noch nicht und darf sie nicht überschreiben.
  const localChanges = useRef(0);

  // Aktive Ansicht der Tab-Navigation (Ausgaben/Kassensturz/Statistiken).
  const [activeTab, setActiveTab] = useState<ListTab>("expenses");

  // Kassensturz (N Personen) – vom Backend berechnet. Startet im Ladezustand,
  // damit die Karte sofort einen Spinner zeigt (ohne setState im Effekt-Body).
  const [settlement, setSettlement] = useState<Settlement | null>(null);
  const [settlementLoading, setSettlementLoading] = useState(true);

  // Bearbeiten / Löschen
  const [editing, setEditing] = useState<Expense | null>(null);
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<Expense | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  // Fehler von List-Aktionen (Löschen), unabhängig vom Ausgabenformular
  const [actionError, setActionError] = useState<string | null>(null);

  // Empty-State-CTA (in ExpenseList) fokussiert das Titelfeld im ExpenseForm
  const titleInputRef = useRef<HTMLInputElement>(null);

  // Bekannte Teilnehmer der Liste (für den Advanced Splitter im Bearbeiten-Modal)
  const participants = useMemo(
    () => collectParticipants(list?.expenses ?? [], list?.members ?? []),
    [list],
  );

  useEffect(() => {
    if (!id) return;
    Promise.all([getList(id), loadMe()])
      .then(([loaded, user]) => {
        setList(loaded);
        setMe(user);
        // Besuch für die Startseite merken: über Home Assistant auf dem Server
        // (alle Geräte), sonst nur in diesem Browser.
        if (user) {
          recordVisit(loaded.id).catch(() => {
            // Komfort: die Liste funktioniert auch ohne Eintrag
          });
        } else {
          addRecentList(loaded.id, loaded.title);
        }
        setShowTutorial(
          shouldShowTutorial(loaded.id) &&
            linkedName(loaded.member_users, user?.id) === null,
        );
      })
      .catch(() => setLoadError("Liste nicht gefunden. Ist der Link korrekt?"));
  }, [id]);

  // Änderungen anderer Geräte und Benutzer übernehmen
  const refreshList = useCallback(() => {
    if (!id) return;
    const changesAtStart = localChanges.current;
    getList(id)
      .then((loaded) => {
        if (localChanges.current !== changesAtStart) return;
        // Unverändert: alten Stand behalten, sonst lädt der Kassensturz neu
        setList((prev) =>
          prev && JSON.stringify(prev) === JSON.stringify(loaded) ? prev : loaded,
        );
      })
      .catch(() => {
        // Netz kurz weg: beim nächsten Durchlauf erneut
      });
  }, [id]);
  useLiveRefresh(refreshList, LIVE_REFRESH_MS);

  /** Eigene Änderung in den State übernehmen (siehe localChanges). */
  const applyLocalChange = useCallback(
    (update: (prev: SharedList) => SharedList) => {
      localChanges.current += 1;
      setList((prev) => (prev ? update(prev) : prev));
    },
    [],
  );

  // Kassensturz vom Backend holen – neu bei jeder Änderung der Ausgabenliste.
  // Das vorige Ergebnis bleibt während des Nachladens sichtbar (kein Flackern).
  // Alle setState-Aufrufe laufen in den Promise-Callbacks (nicht synchron im
  // Effekt-Body), um kaskadierende Renders zu vermeiden.
  useEffect(() => {
    if (!id || !list) return;
    let ignore = false;
    getSettlement(id)
      .then((data) => {
        if (!ignore) setSettlement(data);
      })
      .catch(() => {
        // Kassensturz ist sekundär – Fehler nicht als Blocker behandeln
      })
      .finally(() => {
        if (!ignore) setSettlementLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [id, list]);

  // Neue Ausgabe (aus ExpenseForm) in den lokalen State übernehmen. Die
  // list-Änderung löst automatisch das Nachladen des Kassensturzes aus.
  function handleExpenseAdded(expense: Expense) {
    applyLocalChange((prev) => ({
      ...prev,
      expenses: [...prev.expenses, expense],
    }));
  }

  async function handleEditSave(data: ExpenseUpdate) {
    if (!id || !editing) return;
    setEditSaving(true);
    setEditError(null);
    try {
      const updated = await updateExpense(id, editing.id, data);
      applyLocalChange((prev) => ({
        ...prev,
        expenses: prev.expenses.map((item) =>
          item.id === updated.id ? updated : item,
        ),
      }));
      setEditing(null);
    } catch (error) {
      setEditError(
        withReason("Änderung konnte nicht gespeichert werden", error),
      );
    } finally {
      setEditSaving(false);
    }
  }

  async function handleDeleteConfirm() {
    if (!id || !deleting) return;
    const target = deleting;
    setDeleteBusy(true);
    try {
      await deleteExpense(id, target.id);
      applyLocalChange((prev) => ({
        ...prev,
        expenses: prev.expenses.filter((item) => item.id !== target.id),
      }));
      setDeleting(null);
    } catch (error) {
      setDeleting(null);
      setActionError(withReason("Ausgabe konnte nicht gelöscht werden", error));
    } finally {
      setDeleteBusy(false);
    }
  }

  async function saveMembers(value: MembersValue) {
    if (!id) return;
    const updated = await setMembers(id, value);
    applyLocalChange((prev) => ({
      ...prev,
      members: updated.members,
      member_users: updated.member_users,
    }));
  }

  function closeTutorial() {
    if (id) markTutorialDone(id);
    setShowTutorial(false);
    setFormKey((key) => key + 1);
  }

  // Empty-State-CTA: ins Titelfeld des Formulars scrollen und fokussieren
  function focusTitleInput() {
    titleInputRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
    titleInputRef.current?.focus();
  }

  if (loadError) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-4 text-center">
        <p className="text-lg text-gray-600">{loadError}</p>
        <Link
          to="/"
          className="flex items-center gap-2 rounded-xl px-4 py-3 font-semibold text-emerald-700 transition hover:bg-emerald-50"
        >
          <ArrowLeft className="h-4 w-4" />
          Neue Liste erstellen
        </Link>
      </main>
    );
  }

  if (!list) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-emerald-600" />
      </main>
    );
  }

  // Gesamtsumme in EUR (Basiswährung): Fremdwährungen über ihren Tageskurs
  // umrechnen, damit der Header nicht Beträge verschiedener Währungen mischt.
  const total = list.expenses.reduce(
    (sum, expense) => sum + expense.amount * expense.exchange_rate,
    0,
  );
  const membersValue: MembersValue = {
    members: list.members,
    memberUsers: list.member_users,
  };
  // Die mit dem HA-Benutzer verknüpfte Person (Zahler-Vorschlag)
  const myName = linkedName(list.member_users, me?.id);

  return (
    <main className="mx-auto max-w-2xl px-4 py-6 sm:py-8">
      <ListHeader
        title={list.title}
        expenseCount={list.expenses.length}
        total={total}
        members={list.members}
        onEditMembers={() => setEditingMembers(true)}
      />

      <ListTabs active={activeTab} onChange={setActiveTab} />

      {/* ---------- Tab: Ausgaben (Formular + Liste gehören zusammen) ---------- */}
      {activeTab === "expenses" && (
        <>
          <ExpenseForm
            key={formKey}
            listId={list.id}
            expenses={list.expenses}
            members={list.members}
            linkedPayer={myName}
            onExpenseAdded={handleExpenseAdded}
            titleInputRef={titleInputRef}
          />

          {actionError && (
            <p className="mt-3 text-center text-sm text-red-600">
              {actionError}
            </p>
          )}

          <ExpenseList
            expenses={list.expenses}
            onEdit={(expense) => {
              setEditError(null);
              setEditing(expense);
            }}
            onDelete={(expense) => {
              setActionError(null);
              setDeleting(expense);
            }}
            onAddFirst={focusTitleInput}
          />
        </>
      )}

      {/* ---------- Tab: Kassensturz ---------- */}
      {activeTab === "settlement" && (
        <SettlementCard settlement={settlement} loading={settlementLoading} />
      )}

      {/* ---------- Tab: Statistiken ---------- */}
      {activeTab === "statistics" && (
        <StatisticsBoard expenses={list.expenses} />
      )}

      {/* ---------- Tab: Kontoauszug (Epic 4.0 #3: Upload → Vorschau → Import) ---------- */}
      {activeTab === "bankstatement" && (
        <BankStatementView
          listId={list.id}
          expenses={list.expenses}
          members={list.members}
          linkedPayer={myName}
          onImported={() => {
            // Neue Ausgaben laden → Liste + Kassensturz aktualisieren sich
            getList(list.id)
              .then((loaded) => applyLocalChange(() => loaded))
              .catch(() => {
                // Nachladen ist Komfort – bei Fehler bleibt der alte Stand
              });
          }}
        />
      )}

      {/* ---------- Modale Dialoge ---------- */}
      {showTutorial && (
        <ListTutorial
          listId={list.id}
          initialMembers={membersValue}
          onSaveMembers={saveMembers}
          onClose={closeTutorial}
        />
      )}

      {editingMembers && (
        <MembersDialog
          initial={membersValue}
          onSave={saveMembers}
          onClose={() => setEditingMembers(false)}
        />
      )}

      {editing && (
        <EditExpenseModal
          expense={editing}
          participants={participants}
          categories={categoryOptions(list.expenses)}
          saving={editSaving}
          errorMessage={editError}
          onSave={handleEditSave}
          onCancel={() => setEditing(null)}
        />
      )}

      {deleting && (
        <ConfirmDialog
          title="Ausgabe löschen?"
          message={`„${deleting.title}“ über ${formatMoney(deleting.amount, deleting.currency)} wird dauerhaft entfernt.`}
          confirmLabel="Löschen"
          tone="danger"
          loading={deleteBusy}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleting(null)}
        />
      )}
    </main>
  );
}

export default ListView;
