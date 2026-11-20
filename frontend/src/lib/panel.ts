// Her rolün kendi giriş sayfası vardır. Veli ve öğrenci aynı sayfayı kullanır; kök adres de oraya çıkar.
export type Panel = "veli" | "antrenor" | "yonetici" | "destek";

export const PANEL_YOLU: Record<Panel, string> = {
  veli: "/giris",
  antrenor: "/antrenor-giris",
  yonetici: "/yonetici-giris",
  destek: "/destek-giris",
};

export function rolPaneli(rol: "admin" | "destek" | "antrenor" | "veli" | "ogrenci"): Panel {
  return rol === "admin" ? "yonetici" : rol === "destek" ? "destek" : rol === "antrenor" ? "antrenor" : "veli";
}

// Panel alt alan adları: veli., yonetim., antrenor., destek. Bilinmeyen adreslerde (localhost, demo) null döner ve birleşik davranış sürer.
const ALAN_PANELI: Record<string, Panel> = { veli: "veli", yonetim: "yonetici", antrenor: "antrenor", destek: "destek" };

export function alanPaneli(): Panel | null {
  const etiketler = window.location.hostname.toLowerCase().split(".");
  if (etiketler.length < 2) return null;
  return ALAN_PANELI[etiketler[0]] ?? null;
}

// Panelin giriş sayfası: alt alan adında hep /giris, birleşik kurulumda PANEL_YOLU.
export function girisYolu(panel: Panel): string {
  return alanPaneli() ? "/giris" : PANEL_YOLU[panel];
}
