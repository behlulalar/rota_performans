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
