import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Loader2 } from "lucide-react";
import {
  deleteExpense,
  getList,
  getSettlement,
  updateExpense,
} from "../api";
import type { Expense, ExpenseUpdate, SharedList, Settlement } from "../api";
import ConfirmDialog from "../components/ConfirmDialog";
import EditExpenseModal from "../components/EditExpenseModal";
import ExpenseForm from "../components/ExpenseForm";
import ExpenseList from "../components/ExpenseList";
import ReceiptJobsPanel from "../components/ReceiptJobsPanel";
import BankStatementView from "../components/BankStatementView";
import ListHeader from "../components/ListHeader";
import ListTabs from "../components/ListTabs";
import type { ListTab } from "../components/ListTabs";
import SettlementCard from "../components/SettlementCard";
import StatisticsBoard from "../components/StatisticsBoard";
import { formatEuro } from "../format";
import { addRecentList } from "../recentLists";
import { useReceiptJobs } from "../useReceiptJobs";

/**
 * Detailseite einer geteilten Liste (Route /list/:id).
 *
 * Orchestriert das Laden der Liste, den vom Backend berechneten Kassensturz
 * (Settlement) sowie das Bearbeiten/Löschen einzelner Ausgaben. Die eigentliche
 * Darstellung liegt in fokussierten Teil-Komponenten: ListHeader (Kopf),
 * SettlementCard (Kassensturz), ExpenseForm (Anlegen/Scannen) und ExpenseList.
 */
function ListView() {
  const { id } = useParams<{ id: string }>();

  const [list, setList] = useState<SharedList | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

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

  // Bekannte Teilnehmer der Liste (für den Advanced Splitter im Bearbeiten-Modal):
  // eindeutige Zahler plus alle in bestehenden Aufteilungen genannten Namen.
  const participants = useMemo(() => {
    const names: string[] = [];
    for (const expense of list?.expenses ?? []) {
      if (!names.includes(expense.payer_name)) names.push(expense.payer_name);
      for (const name of Object.keys(expense.splits ?? {})) {
        if (!names.includes(name)) names.push(name);
      }
    }
    return names;
  }, [list]);

  useEffect(() => {
    if (!id) return;
    getList(id)
      .then((loaded) => {
        setList(loaded);
        // Besuch für die Startseite merken (UUID + Titel + jetzt), rein lokal.
        addRecentList(loaded.id, loaded.title);
      })
      .catch(() =>
        setLoadError("Liste nicht gefunden. Ist der Link korrekt?"),
      );
  }, [id]);

  // Bon-Scans im Hintergrund verfolgen (Bugfix 2026-09-25): Ist ein Scan
  // fertig, die Liste frisch laden – die neue Ausgabe erscheint so automatisch
  // (und der Kassensturz rechnet über die list-Änderung neu).
  const receiptJobs = useReceiptJobs(id, () => {
    if (!id) return;
    getList(id)
      .then(setList)
      .catch(() => {
        // Nachladen ist Komfort – bei Fehler bleibt der alte Stand sichtbar
      });
  });

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
    setList((prev) =>
      prev ? { ...prev, expenses: [...prev.expenses, expense] } : prev,
    );
  }

  async function handleEditSave(data: ExpenseUpdate) {
    if (!id || !editing) return;
    setEditSaving(true);
    setEditError(null);
    try {
      const updated = await updateExpense(id, editing.id, data);
      setList((prev) =>
        prev
          ? {
              ...prev,
              expenses: prev.expenses.map((item) =>
                item.id === updated.id ? updated : item,
              ),
            }
          : prev,
      );
      setEditing(null);
    } catch {
      setEditError("Änderung konnte nicht gespeichert werden.");
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
      setList((prev) =>
        prev
          ? {
              ...prev,
              expenses: prev.expenses.filter((item) => item.id !== target.id),
            }
          : prev,
      );
      setDeleting(null);
    } catch {
      setDeleting(null);
      setActionError("Ausgabe konnte nicht gelöscht werden.");
    } finally {
      setDeleteBusy(false);
    }
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

  return (
    <main className="mx-auto max-w-2xl px-4 py-6 sm:py-8">
      <ListHeader
        title={list.title}
        expenseCount={list.expenses.length}
        total={total}
      />

      <ListTabs active={activeTab} onChange={setActiveTab} />

      {/* ---------- Tab: Ausgaben (Formular + Liste gehören zusammen) ---------- */}
      {activeTab === "expenses" && (
        <>
          <ExpenseForm
            listId={list.id}
            expenses={list.expenses}
            onExpenseAdded={handleExpenseAdded}
            onReceiptQueued={receiptJobs.refresh}
            titleInputRef={titleInputRef}
          />

          <ReceiptJobsPanel
            jobs={receiptJobs.jobs}
            onDismiss={receiptJobs.dismiss}
            onConfirmDuplicate={receiptJobs.confirmDuplicate}
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
          onImported={() => {
            // Neue Ausgaben laden → Liste + Kassensturz aktualisieren sich
            getList(list.id)
              .then(setList)
              .catch(() => {
                // Nachladen ist Komfort – bei Fehler bleibt der alte Stand
              });
          }}
        />
      )}

      {/* ---------- Modale Dialoge ---------- */}
      {editing && (
        <EditExpenseModal
          expense={editing}
          participants={participants}
          saving={editSaving}
          errorMessage={editError}
          onSave={handleEditSave}
          onCancel={() => setEditing(null)}
        />
      )}

      {deleting && (
        <ConfirmDialog
          title="Ausgabe löschen?"
          message={`"${deleting.title}" über ${formatEuro(deleting.amount)} wird dauerhaft entfernt.`}
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
