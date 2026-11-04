import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import GuncellemeBildirimi from "./components/GuncellemeBildirimi";
import { serviceWorkerKaydet } from "./lib/pwa";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
    <GuncellemeBildirimi />
  </StrictMode>,
);

// Service worker ve güncelleme akışı yalnızca üretim derlemesinde çalışır (lib/pwa.ts).
serviceWorkerKaydet();
