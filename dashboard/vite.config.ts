import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy /api/* to the FastAPI control plane so the browser makes same-origin
// calls (no CORS). Start the backend with:  uvicorn main:app  (port 8000)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
