import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import dns from "node:dns";

// Windows에서 localhost가 ::1로 가면 Cursor 내장 브라우저가 안 열린다.
dns.setDefaultResultOrder("verbatim");

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: "localhost",
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
