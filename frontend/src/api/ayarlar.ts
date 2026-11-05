import { api } from "../lib/api";

export type Ayarlar = {
  ad: string;
  telefon: string | null;
  eposta: string | null;
  adres: string | null;
  instagram: string | null;
  geri_alma_dakika: number;
  azaldi_esigi: number;
  wa_saatlik_limit: number;
  wa_gunluk_limit: number;
  wa_baslangic_saat: number;
  wa_bitis_saat: number;
  wa_push_varsa_atla: boolean;
};

export const ayarlariGetir = () => api<Ayarlar>("/api/ayarlar");
export const ayarlariGuncelle = (g: Partial<Ayarlar>) =>
  api<Ayarlar>("/api/ayarlar", { method: "PUT", body: JSON.stringify(g) });

export type KulupIletisim = Pick<Ayarlar, "ad" | "telefon" | "eposta" | "adres" | "instagram">;
export const iletisimGetir = () => api<KulupIletisim>("/api/ayarlar/iletisim");

export type KulupTanitim = Pick<Ayarlar, "ad" | "instagram">;
export const tanitimGetir = () => api<KulupTanitim>("/api/ayarlar/tanitim");
