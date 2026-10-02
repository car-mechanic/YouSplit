import { AlertTriangle, Loader2, X } from "lucide-react";
import type { ReceiptJob } from "../api";

interface ReceiptJobsPanelProps {
  jobs: ReceiptJob[];
  onDismiss: (jobId: string) => void;
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
 * beim einmaligen Modell-Download) und fehlgeschlagene Scans mit Ursache und
 * „Verwerfen"-Button. Erfolgreiche Scans tauchen hier nicht auf – sie landen
 * direkt in der Ausgabenliste. Rendert nichts, wenn es keine Jobs gibt.
 */
function ReceiptJobsPanel({ jobs, onDismiss }: ReceiptJobsPanelProps) {
  if (jobs.length === 0) return null;

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
