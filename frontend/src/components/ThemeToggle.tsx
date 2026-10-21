import { useState } from "react";
import { Moon, Sun } from "lucide-react";
import { applyTheme, getInitialTheme, type Theme } from "../theme";

/** Kleiner Schalter für Hell/Dunkel; der Zustand wird beim Start aus theme.ts gelesen. */
function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => {
    const initial = getInitialTheme();
    applyTheme(initial);
    return initial;
  });

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    setTheme(next);
  }

  const label = theme === "dark" ? "Helles Design" : "Dunkles Design";
  return (
    <button
      type="button"
      onClick={toggle}
      title={label}
      aria-label={label}
      className="rounded-full p-2 text-gray-500 transition hover:bg-gray-200 hover:text-gray-900"
    >
      {theme === "dark" ? (
        <Sun className="h-5 w-5" />
      ) : (
        <Moon className="h-5 w-5" />
      )}
    </button>
  );
}

export default ThemeToggle;
