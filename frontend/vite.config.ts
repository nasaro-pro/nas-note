import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import dns from "node:dns";

dns.setDefaultResultOrder("verbatim");
const noProxy = [process.env.NO_PROXY, process.env.no_proxy, "127.0.0.1", "localhost", "::1"]
  .filter(Boolean)
  .join(",");
process.env.NO_PROXY = noProxy;
process.env.no_proxy = noProxy;

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
        ws: true,
        timeout: 0,
        proxyTimeout: 0,
        configure(proxy) {
          proxy.on("error", (err, _req, res) => {
            console.error("api proxy", err.message);
            const payload = JSON.stringify({
              detail: "백엔드에 연결하지 못했습니다. start.bat을 다시 실행하세요.",
            });
            if (res && "headersSent" in res && !res.headersSent && "writeHead" in res) {
              (res as { writeHead: (code: number, headers: Record<string, string>) => void }).writeHead(502, {
                "Content-Type": "application/json; charset=utf-8",
              });
              (res as { end: (body: string) => void }).end(payload);
            }
          });
        },
      },
    },
  },
});
