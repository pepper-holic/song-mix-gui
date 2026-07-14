import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// QWebEngineView가 file:// 로 로드하므로 상대 경로 base 필수
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { outDir: "dist", assetsInlineLimit: 0 },
});
