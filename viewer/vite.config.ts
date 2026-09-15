import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// VITE_BASE is set by the GitHub Pages workflow to "/<repo-name>/".
export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE ?? "/",
  build: { chunkSizeWarningLimit: 1500 },
});
