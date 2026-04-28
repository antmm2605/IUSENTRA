import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

const flaskDevUrl = process.env.IUSENTRA_FLASK_DEV_URL || "http://localhost:8080";

export default defineConfig({
  plugins: [react()],
  base: "/static/react/",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": flaskDevUrl,
      "/logout": flaskDevUrl,
    },
  },
  build: {
    outDir: "../web/static/react",
    emptyOutDir: true,
    manifest: true,
    sourcemap: false,
    assetsDir: "assets",
    rollupOptions: {
      input: "src/main.tsx",
    },
  },
});
