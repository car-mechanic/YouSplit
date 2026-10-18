import { useEffect, useRef } from "react";

/**
 * Hält eine Ansicht mit dem Server synchron, wenn andere Geräte etwas ändern.
 *
 * Ruft `refresh` in festem Abstand auf, solange der Tab sichtbar ist, und
 * sofort, wenn er wieder sichtbar wird (Handy entsperrt, Tab gewechselt).
 * Polling statt Push: läuft unverändert durch den HA-Ingress, den direkten
 * Port und Cloudflare, und die Datenmengen einer Liste sind klein.
 */
export function useLiveRefresh(refresh: () => void, intervalMs: number): void {
  // Immer die neueste Funktion aufrufen, ohne Timer neu zu starten
  const latest = useRef(refresh);
  useEffect(() => {
    latest.current = refresh;
  }, [refresh]);

  useEffect(() => {
    // focus und visibilitychange kommen beim Zurückkehren meist zusammen
    let lastRun = 0;
    const tick = () => {
      if (document.visibilityState !== "visible") return;
      if (Date.now() - lastRun < 1000) return;
      lastRun = Date.now();
      latest.current();
    };
    const timer = window.setInterval(tick, intervalMs);
    document.addEventListener("visibilitychange", tick);
    window.addEventListener("focus", tick);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", tick);
      window.removeEventListener("focus", tick);
    };
  }, [intervalMs]);
}
