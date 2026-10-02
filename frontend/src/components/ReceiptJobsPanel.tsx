import { useState } from "react";
import { AlertTriangle, CopyCheck, Loader2, X } from "lucide-react";
import type { ReceiptJob } from "../api";

interface ReceiptJobsPanelProps {
  jobs: ReceiptJob[];
  onDismiss: (jobId: string) => void;
  /** Doppelten Bon „trotzdem hinzufügen“ – wirft bei Fehlern. */
  onConfirmDuplicate: (jobId: string) => Promise<void>;
}

/** Uhrzeit "HH:MM" eines ISO-Zeitstempels (lokale Zeitzone). */
function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("de-DE", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

/**
 * Status der Bon-Scans im Hintergrund (Bugfix 2026-09-25).
 *
 * Zeigt laufende Scans mit Spinner (plus optionalem Fortschritts-Hinweis, etwa
 * beim einmaligen Modell-Download), fehlgeschlagene Scans mit Ursache und
 * „Verwerfen"-Button sowie **doppelte Bons** (gleiches Geschäft, gleicher Betrag,
 * gleiches Datum) mit „Verwerfen" und „Trotzdem hinzufügen". Erfolgreiche Scans
 * tauchen hier nicht auf – sie landen direkt in der Ausgabenliste. Rendert nichts,
 * wenn es keine Jobs gibt.
 */
function ReceiptJobsPanel({
  jobs,
  onDismiss,
  onConfirmDuplicate,
}: ReceiptJobsPanelProps) {
  // Welcher Duplikat-Job gerade bestätigt wird + ggf. die Fehlermeldung dazu
  const [busyId, setBusyId] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  if (jobs.length === 0) return null;

  async function confirm(jobId: string) {
    setBusyId(jobId);
    setConfirmError(null);
    try {
      await onConfirmDuplicate(jobId);
    } catch (error) {
      setConfirmError(
        error instanceof Error
          ? error.message
          : "Der Bon konnte nicht hinzugefügt werden.",
      );
    } finally {
      setBusyId(null);
    }
  }

  return (
    <ul className="mt-4 space-y-2" aria-live="polite">
      {jobs.map((job) => {
        const label = job.filename ? `„${job.filename}"` : "Beleg";
        const meta = `${job.payer_name} · ${formatTime(job.created_at)} Uhr`;

        if (job.status === "failed") {
          return (
            <li
              key={job.id}
              className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
            >
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
              <div className="min-w-0 flex-1">
                <p className="font-semibold">
                  {label} konnte nicht verarbeitet werden
                </p>
                <p className="mt-0.5 break-words">
                  {job.error ?? "Unbekannter Fehler."}
                </p>
                <p className="mt-1 text-xs text-red-600/80">{meta}</p>
              </div>
              <button
                type="button"
                onClick={() => onDismiss(job.id)}
                className="rounded-lg p-1 text-red-500 transition hover:bg-red-100 hover:text-red-700"
                aria-label="Fehlermeldung verwerfen"
                title="Verwerfen"
              >
                <X className="h-4 w-4" />
              </button>
            </li>
          );
        }

        if (job.status === "duplicate") {
          const busy = busyId === job.id;
          return (
            <li
              key={job.id}
              className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
            >
              <div className="flex items-start gap-3">
                <CopyCheck className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{label} ist ein Duplikat</p>
                  <p className="mt-0.5 break-words">
                    {job.detail ?? "Dieser Bon ist bereits in der Liste."}
                  </p>
                  <p className="mt-1 text-xs text-amber-700/80">{meta}</p>
                </div>
              </div>
              {confirmError && busyId === null && (
                <p className="mt-2 text-xs text-red-700">{confirmError}</p>
              )}
              <div className="mt-3 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={() => onDismiss(job.id)}
                  disabled={busy}
                  className="rounded-lg border border-amber-300 px-3 py-2 text-sm font-semibold text-amber-900 transition hover:bg-amber-100 disabled:opacity-50"
                >
                  Verwerfen
                </button>
                <button
                  type="button"
                  onClick={() => void confirm(job.id)}
                  disabled={busy}
                  className="flex items-center justify-center gap-2 rounded-lg bg-amber-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {busy ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    "Trotzdem hinzufügen"
                  )}
                </button>
              </div>
            </li>
          );
        }

        return (
          <li
            key={job.id}
            className="flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
          >
            <Loader2 className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-emerald-600" />
            <div className="min-w-0 flex-1">
              <p className="font-semibold">
                {label} wird im Hintergrund verarbeitet …
              </p>
              <p className="mt-0.5">
                {job.detail ??
                  "Die Ausgabe erscheint automatisch in der Liste. Du kannst die App auch schließen."}
              </p>
              <p className="mt-1 text-xs text-emerald-700/70">{meta}</p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export default ReceiptJobsPanel;
