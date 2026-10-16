/**
 * Basis-Pfad der App und teilbare Links.
 *
 * Im Home-Assistant-Ingress läuft die App unter `/api/hassio_ingress/<token>/`.
 * Das Backend schreibt dieses Präfix als `<base href>` in die index.html
 * (frontend_static.py). Direkt aufgerufen ist die Basis `/`.
 */

/** Router-Basis: "" direkt, "/api/hassio_ingress/<token>" im Ingress. */
export function routerBasename(baseUri: string = document.baseURI): string {
  return new URL(baseUri).pathname.replace(/\/$/, "");
}

/**
 * Link zum Teilen. Im Ingress zeigt die Adresse auf Home Assistant (Login
 * nötig). Mit gesetzter `public_url` (Add-on-Option) wird der App-Pfad
 * deshalb an die öffentliche Adresse gehängt.
 */
export function shareableUrl(href: string, baseUri: string, publicUrl: string): string {
  if (!publicUrl) return href;
  const url = new URL(href);
  const appPath = url.pathname.slice(routerBasename(baseUri).length);
  return publicUrl.replace(/\/$/, "") + appPath + url.search + url.hash;
}

/** Öffentliche Adresse aus dem Meta-Tag, das das Backend befüllt. */
export function publicUrl(): string {
  return (
    document.querySelector('meta[name="yousplit-public-url"]')?.getAttribute("content") ?? ""
  );
}
