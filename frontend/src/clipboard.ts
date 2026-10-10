/**
 * Kopiert Text in die Zwischenablage – auch ohne HTTPS.
 *
 * `navigator.clipboard` gibt es nur in "sicheren Kontexten" (HTTPS oder
 * localhost). Ruft man die App im Heimnetz über http://192.168… auf, fehlt die
 * API komplett. Dann greift der alte Weg über ein unsichtbares Textfeld und
 * `document.execCommand("copy")`, der in allen gängigen Browsern noch geht.
 *
 * @returns `true`, wenn das Kopieren geklappt hat.
 */
export async function copyText(text: string): Promise<boolean> {
  if (window.isSecureContext && navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // z. B. fehlende Berechtigung: unten den Fallback versuchen
    }
  }
  return copyWithTextarea(text);
}

/** Fallback: Text in ein verstecktes Textfeld legen, markieren, kopieren. */
function copyWithTextarea(text: string): boolean {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  // readonly verhindert, dass auf dem Handy die Tastatur aufklappt
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "0";
  textarea.style.left = "0";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  // iOS Safari markiert per select() nicht zuverlässig
  textarea.setSelectionRange(0, text.length);
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch {
    ok = false;
  }
  document.body.removeChild(textarea);
  return ok;
}

/**
 * Kopiert den Link der aktuellen Seite. Klappt das gar nicht, wird der Link
 * in einem Eingabedialog angezeigt, damit man ihn von Hand kopieren kann.
 */
export async function copyCurrentLink(): Promise<boolean> {
  const url = window.location.href;
  const ok = await copyText(url);
  if (!ok) window.prompt("Link zum Kopieren:", url);
  return ok;
}
