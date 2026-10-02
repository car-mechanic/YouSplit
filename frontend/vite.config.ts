import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  // tailwindcss() generiert die Tailwind-v4-Utilities aus `@import "tailwindcss"`.
  // Ohne dieses Plugin bleiben alle Utility-Klassen wirkungslos (ungestyltes UI).
  plugins: [react(), tailwindcss()],
})
