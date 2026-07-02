import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "boi_api/app/static/dist",
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      input: "frontend/ops-center/src/main.tsx",
      output: {
        entryFileNames: "ops-center.js",
        chunkFileNames: "ops-center-[name].js",
        assetFileNames: "ops-center.[ext]"
      }
    }
  }
});
