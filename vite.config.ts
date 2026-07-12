import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "boi_api/app/static/dist",
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      input: {
        "ops-center": "frontend/ops-center/src/main.tsx",
        "knowledge-graph": "frontend/knowledge-graph/src/main.ts"
      },
      output: {
        entryFileNames: "[name].js",
        chunkFileNames: "[name]-[hash].js",
        assetFileNames: "[name].[ext]"
      }
    }
  }
});
