import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/",
  plugins: [react()],
  build: {
    outDir: "../dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/youtube": "http://127.0.0.1:8000",
      "/spotify": "http://127.0.0.1:8000",
      "/playlist": "http://127.0.0.1:8000",
      "/feedback": "http://127.0.0.1:8000",
      "/qa": "http://127.0.0.1:8000",
      "/sessions": "http://127.0.0.1:8000",
    },
  },
});
