import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  // Relative Asset-Pfade: lösen gegen das <base href> auf (HA-Ingress-Präfix)
  base: './',
  // tailwindcss() generiert die Tailwind-v4-Utilities aus `@import "tailwindcss"`.
  // Ohne dieses Plugin bleiben alle Utility-Klassen wirkungslos (ungestyltes UI).
  plugins: [react(), tailwindcss()],
  server: {
    // Zugriff ueber beliebige Hostnamen im Heimnetz erlauben
    // (z. B. Servername statt IP-Adresse)
    allowedHosts: true,
    proxy: {
      // API-Aufrufe serverseitig an den Backend-Container weiterreichen.
      // "backend" ist der Service-Name aus docker-compose.yml.
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
})
