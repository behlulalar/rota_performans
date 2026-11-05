import { api } from "../lib/api";

export type WhatsAppDurumu = "yapilandirilmadi" | "ulasilamiyor" | "bagli_degil" | "baglaniyor" | "bagli";
export type DevreKesici = { acik: boolean; sebep: string | null };
export type WhatsAppBaglanti = {
  durum: WhatsAppDurumu;
  numara: string | null;
  profil_adi: string | null;
  qr: string | null;
  devre_kesici: DevreKesici;
  bekleyen_sayisi: number;
};

export const whatsappGetir = () => api<WhatsAppBaglanti>("/api/whatsapp");
export const whatsappBaglan = () => api<WhatsAppBaglanti>("/api/whatsapp/baglan", { method: "POST" });
export const whatsappKes = () => api<WhatsAppBaglanti>("/api/whatsapp/kes", { method: "POST" });
