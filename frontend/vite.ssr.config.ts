import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Pre-generazione del sito pubblico dello studio: un solo file ESM eseguito dal binario Node copiato
 * nell'immagine (nessun node_modules a runtime: React è incluso nel file). Uscita fuori da static/,
 * quindi non servita al pubblico.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': new URL('./src', import.meta.url).pathname,
    },
  },
  ssr: {
    noExternal: true,
    target: 'node',
  },
  build: {
    ssr: 'src/sitoPubblico/ssrSito.tsx',
    outDir: '../web/sito_pubblico_ssr',
    emptyOutDir: true,
    target: 'node20',
    minify: true,
    copyPublicDir: false,
    rollupOptions: {
      output: { format: 'esm', entryFileNames: 'sito-pubblico-ssr.mjs' },
    },
  },
})
