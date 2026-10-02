/**
 * Fortschrittsanzeige für Bon-Scans.
 *
 * Ollama liefert während der KI-Analyse keinen echten Fortschritt (ein einziger
 * Aufruf, der lange dauert). Deshalb meldet das Backend nur **Meilensteine**
 * (`ReceiptJob.progress`), und zwischen zwei Meilensteinen **schätzt** das
 * Frontend aus der verstrichenen Zeit – anhand der Dauer der letzten Scans
 * (`estimated_seconds`). Der Balken läuft dabei nie über den nächsten Meilenstein
 * hinaus und erreicht 100 % erst, wenn der Scan wirklich fertig ist.
 */

/** Meilensteine – Spiegel von `receipt_jobs.PROGRESS_*` im Backend. */
export const PROGRESS = {
  ACCEPTED: 5,
  ANALYZING: 10,
  ANALYZED: 85,
  CHECKED: 90,
  SAVING: 95,
} as const;

/** Obergrenze der Schätzung, solange der Scan noch läuft. */
const MAX_WHILE_RUNNING = 99;

/** Dauer der kurzen Abschnitte (außer der KI-Analyse), in Sekunden. */
const SHORT_STAGE_SECONDS = 4;

/** Startwert, falls das Backend (noch) keine Schätzung mitliefert. */
const FALLBACK_ANALYSIS_SECONDS = 60;

const MILESTONES: readonly number[] = [
  PROGRESS.ACCEPTED,
  PROGRESS.ANALYZING,
  PROGRESS.ANALYZED,
  PROGRESS.CHECKED,
  PROGRESS.SAVING,
];

/** Der nächste Meilenstein oberhalb von `progress` (sonst 99 %). */
export function nextMilestone(progress: number): number {
  return MILESTONES.find((milestone) => milestone > progress) ?? MAX_WHILE_RUNNING;
}

/** Klartext zum aktuellen Abschnitt. */
export function stageLabel(progress: number): string {
  if (progress < PROGRESS.ANALYZING) return "Bon angenommen …";
  if (progress < PROGRESS.ANALYZED) return "Bon wird gelesen …";
  if (progress < PROGRESS.SAVING) return "Betrag und Duplikate werden geprüft …";
  return "Ausgabe wird gespeichert …";
}

/**
 * Geschätzter Fortschritt (0–99) zwischen dem gemeldeten Meilenstein und dem
 * nächsten. Kurve: schnell am Anfang, dann abflachend (nähert sich dem nächsten
 * Meilenstein nur an) – nach der erwarteten Dauer sind ~95 % der Strecke erreicht.
 *
 * @param progress  zuletzt vom Backend gemeldeter Meilenstein
 * @param elapsedSeconds  Zeit seit der Meldung dieses Meilensteins
 * @param estimatedSeconds  erwartete Dauer der KI-Analyse (aus den letzten Scans)
 */
export function estimateProgress(
  progress: number,
  elapsedSeconds: number,
  estimatedSeconds: number | null,
): number {
  const base = Math.min(progress, MAX_WHILE_RUNNING);
  const cap = nextMilestone(progress);
  const inAnalysis = progress >= PROGRESS.ANALYZING && progress < PROGRESS.ANALYZED;
  const stageSeconds = inAnalysis
    ? (estimatedSeconds ?? FALLBACK_ANALYSIS_SECONDS)
    : SHORT_STAGE_SECONDS;
  const tau = Math.max(stageSeconds, 1) / 3;
  const fraction = 1 - Math.exp(-Math.max(elapsedSeconds, 0) / tau);
  return base + (cap - base) * fraction;
}
