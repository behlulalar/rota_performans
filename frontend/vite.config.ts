import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig, type Plugin } from "vite";

// Geliştirmede /api istekleri backend'e yönlendirilir. Çerezler aynı kökenden geldiği için
// CORS ve üçüncü taraf çerez sorunu yaşanmaz. Üretimde aynı işi Caddy yapar.
const apiHedef = process.env.API_PROXY_TARGET ?? "http://localhost:8100";

// nginx.conf'taki host eşlemesinin geliştirme karşılığı: yonetim./antrenor./destek. alt alanlarında
// manifest, favicon ve apple-touch-icon isteklerini panelin kendi dosyalarına çevirir.
function panelSimgeleri(): Plugin {
  const adres = /^\/(manifest)\.webmanifest|^\/(apple-touch-icon|favicon)\.png/;
  return {
    name: "rota-panel-simgeleri",
    configureServer(sunucu) {
      sunucu.middlewares.use((istek, _yanit, sonraki) => {
        const host = (istek.headers.host ?? "").toLowerCase();
        const panel = /^(yonetim|antrenor|destek)\./.exec(host)?.[1];
        const [yol, sorgu] = (istek.url ?? "").split("?");
        const e = panel && adres.exec(yol);
        if (e) {
          const hedef = e[1] ? `/manifest-${panel}.webmanifest` : `/${e[2]}-${panel}.png`;
          if (existsSync(resolve(__dirname, "public", hedef.slice(1)))) istek.url = hedef + (sorgu ? `?${sorgu}` : "");
        }
        sonraki();
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), panelSimgeleri()],
  server: {
    allowedHosts: [".localhost"],
    proxy: { "/api": { target: apiHedef, changeOrigin: false } },
  },
});
