import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Geliştirmede /api istekleri backend'e yönlendirilir. Çerezler aynı kökenden geldiği için
// CORS ve üçüncü taraf çerez sorunu yaşanmaz. Üretimde aynı işi Caddy yapar.
const apiHedef = process.env.API_PROXY_TARGET ?? "http://localhost:8100";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { "/api": { target: apiHedef, changeOrigin: true } },
  },
});
