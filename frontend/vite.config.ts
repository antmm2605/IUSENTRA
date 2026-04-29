import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/static/react/',
  build: {
    outDir: '../web/static/react',
    emptyOutDir: true,
    manifest: true,
    rollupOptions: { input: './index.html' }
  },
  server: {
    proxy: {
      '/api': 'http://localhost:5000',
      '/app-v2': 'http://localhost:5000'
    }
  }
})
