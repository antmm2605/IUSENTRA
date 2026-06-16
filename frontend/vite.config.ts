import { defineConfig } from 'vite'
import type { Plugin } from 'vite'
import react from '@vitejs/plugin-react'

function sanitizeGeneratedText(): Plugin {
  const mojibakePattern = new RegExp(
    String.raw`\u00c3.|\u00c2.|\u00e2[\u20ac\u201a\u0192\u201e\u2026\u2020\u2021\u02c6\u2030\u0160\u2039\u0152\u017d\u2018\u2019\u201c\u201d\u2022\u2013\u2014\u02dc\u2122\u0161\u203a\u0153\u017e\u0178]|\u00e2\u0153.|\u00e2\u0161.`,
    'g',
  )

  const sanitize = (source: string) => source.replace(mojibakePattern, 'v').replace(/[ \t]+$/gm, '')

  return {
    name: 'iusentra-sanitize-generated-text',
    generateBundle(_options, bundle) {
      for (const item of Object.values(bundle)) {
        if (item.type === 'chunk') {
          item.code = sanitize(item.code)
        } else if (item.type === 'asset' && typeof item.source === 'string') {
          item.source = sanitize(item.source)
        }
      }
    },
  }
}

export default defineConfig({
  plugins: [react(), sanitizeGeneratedText()],
  base: '/static/react/',
  resolve: {
    alias: {
      '@': new URL('./src', import.meta.url).pathname,
      '@iusentra-data': new URL('../pct/data', import.meta.url).pathname,
    },
  },
  build: {
    outDir: '../web/static/react',
    target: 'es2022',
    // I chunk Vite hanno nomi hashati e possono restare in cache nei browser
    // autenticati durante un deploy. Non svuotare la directory evita 404 sui
    // bundle ancora referenziati da una shell caricata prima dell'aggiornamento.
    emptyOutDir: false,
    manifest: true,
    rollupOptions: {
      input: './index.html',
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('/node_modules/lucide-react/')) {
            return 'vendor-icons'
          }
          return 'vendor'
        },
      },
    }
  },
  server: {
    proxy: {
      '/api': 'http://localhost:5000',
      '/app-v2': 'http://localhost:5000'
    }
  }
})
