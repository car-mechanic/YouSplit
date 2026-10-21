export type Theme = "light" | "dark";

const STORAGE_KEY = "yousplit-theme";

/** Gespeicherte Wahl, sonst die Systemeinstellung. Das Design ist reine Geräte-Vorliebe, daher localStorage. */
export function getInitialTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // localStorage kann gesperrt sein (z. B. im Ingress-iframe): dann Systemwert
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle("dark", theme === "dark");
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Wahl gilt dann nur für diese Sitzung
  }
}
