import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// During development (npm run dev, port 5173) the browser calls /api/... on 5173.
// Vite forwards those calls to Nginx on port 80, so the dev page also talks to the
// real load-balanced API, with no CORS setup needed.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:80",
      "/health": "http://localhost:80",
    },
  },
});
