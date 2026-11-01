import { api } from "../lib/api";

export type Ayarlar = {
  ad: string;
  telefon: string | null;
  eposta: string | null;
  adres: string | null;
  geri_alma_dakika: number;
  azaldi_esigi: number;
};

export const ayarlariGetir = () => api<Ayarlar>("/api/ayarlar");
export const ayarlariGuncelle = (g: Partial<Ayarlar>) =>
  api<Ayarlar>("/api/ayarlar", { method: "PUT", body: JSON.stringify(g) });

export type KulupIletisim = Pick<Ayarlar, "ad" | "telefon" | "eposta" | "adres">;
export const iletisimGetir = () => api<KulupIletisim>("/api/ayarlar/iletisim");
