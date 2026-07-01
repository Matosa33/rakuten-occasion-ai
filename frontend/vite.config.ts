import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Cycle 10.1 - Vite + React + Tailwind v4.
// Proxy /api → backend FastAPI (uvicorn :8000) pour éviter le CORS en dev.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        // 127.0.0.1 (PAS localhost) : évite l'ECONNREFUSED IPv6/IPv4 - uvicorn
        // bind 127.0.0.1 (IPv4) alors que Node résout localhost en ::1 (IPv6) d'abord.
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
