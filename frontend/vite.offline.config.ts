import {defineConfig} from 'vite'
import react from '@vitejs/plugin-react'
// Separate, generic public shell. No server-rendered user/studio data.
export default defineConfig({
  publicDir:false, plugins:[react()], base:'/static/offline-workspace/',
  build:{outDir:'../web/static/offline-workspace',emptyOutDir:true,modulePreload:false,
    rollupOptions:{input:'./offline.html',output:{entryFileNames:'workspace.js',assetFileNames:'workspace.[ext]',inlineDynamicImports:true}}},
})
