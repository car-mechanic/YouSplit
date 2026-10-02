import { useCallback, useEffect, useRef, useState } from "react";
import { dismissReceiptJob, getReceiptJobs } from "./api";
import type { ReceiptJob } from "./api";

/** Abfrage-Intervall, solange mindestens ein Bon verarbeitet wird. */
const POLL_INTERVAL_MS = 4000;

interface UseReceiptJobsResult {
  /** Laufende und fehlgeschlagene Scans (erledigte werden automatisch quittiert). */
  jobs: ReceiptJob[];
  /** Sofort neu abfragen – z. B. direkt nach einem Upload. */
  refresh: () => void;
  /** Fehlgeschlagenen (oder hängenden) Scan ausblenden und im Backend löschen. */
  dismiss: (jobId: string) => void;
}

/**
 * Verfolgt die asynchronen Bon-Scans einer Liste (Bugfix 2026-09-25).
 *
 * Hintergrund: Seit dem „Fire & Forget"-Upload (Roadmap 4.0 #2) bekam das
 * Frontend nur ein 202 zurück – ob der Scan im Hintergrund klappte, erfuhr der
 * Nutzer nie. Dieser Hook fragt den Status per Polling ab:
 *
 * - Solange ein Job `processing` ist, wird alle {@link POLL_INTERVAL_MS} ms neu
 *   abgefragt; sonst ruht das Polling (kein Dauer-Traffic).
 * - Ist ein Job `done`, wird `onJobsCompleted` aufgerufen (→ Liste neu laden)
 *   und der Job im Backend quittiert.
 * - `failed`-Jobs bleiben sichtbar, bis der Nutzer sie verwirft.
 *
 * Beim Öffnen der Liste wird einmal abgefragt – so sieht man auch Scans, die
 * liefen oder scheiterten, während die App geschlossen war.
 */
export function useReceiptJobs(
  listId: string | undefined,
  onJobsCompleted: () => void,
): UseReceiptJobsResult {
  const [jobs, setJobs] = useState<ReceiptJob[]>([]);
  // Ein Hochzählen startet den Polling-Effekt neu (sofortige Abfrage).
  const [refreshToken, setRefreshToken] = useState(0);

  // Callback per Ref, damit ein neuer Callback-Identität den Effekt nicht neu
  // startet (ListView übergibt eine Inline-Funktion).
  const onCompletedRef = useRef(onJobsCompleted);
  useEffect(() => {
    onCompletedRef.current = onJobsCompleted;
  });

  useEffect(() => {
    if (!listId) return;
    const id = listId;
    let cancelled = false;
    let timer: number | undefined;
    // Ob beim letzten erfolgreichen Abruf noch etwas lief – nur dann lohnt sich
    // nach einem Netzfehler ein erneuter Versuch.
    let hadProcessing = false;

    async function poll() {
      try {
        const loaded = await getReceiptJobs(id);
        if (cancelled) return;

        const finished = loaded.filter((job) => job.status === "done");
        if (finished.length > 0) {
          onCompletedRef.current();
          for (const job of finished) {
            // Quittieren ist "best effort" – schlägt es fehl, kommt der Job beim
            // nächsten Abruf einfach noch einmal (Neuladen ist harmlos).
            dismissReceiptJob(id, job.id).catch(() => undefined);
          }
        }

        const visible = loaded.filter((job) => job.status !== "done");
        setJobs(visible);
        hadProcessing = visible.some((job) => job.status === "processing");
      } catch {
        // Backend kurz weg (z. B. Reload) – Zustand beibehalten, ggf. weiter pollen
        if (cancelled) return;
      }
      if (hadProcessing) {
        timer = window.setTimeout(poll, POLL_INTERVAL_MS);
      }
    }

    void poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [listId, refreshToken]);

  const refresh = useCallback(() => setRefreshToken((token) => token + 1), []);

  const dismiss = useCallback(
    (jobId: string) => {
      if (!listId) return;
      // Optimistisch ausblenden; das Backend-DELETE ist idempotent.
      setJobs((prev) => prev.filter((job) => job.id !== jobId));
      dismissReceiptJob(listId, jobId).catch(() => undefined);
    },
    [listId],
  );

  return { jobs, refresh, dismiss };
}
