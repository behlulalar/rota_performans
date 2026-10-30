import { api } from "../lib/api";
import type { OdemeYontemi, OgrenciPaketi } from "./paket";

export type { OdemeYontemi };

export const YONTEM_ETIKET: Record<OdemeYontemi, string> = {
  nakit: "Nakit",
  havale_eft: "Havale/EFT",
  diger: "Diğer",
};

export type OdemeKaydi = {
  id: string;
  tarih: string;
  ogrenci: { id: string; ad: string; soyad: string };
  paket_adi: string;
  tutar: string | null;
  yontem: OdemeYontemi;
  aciklama?: string | null;
  iptal: boolean;
  iptal_nedeni?: string | null;
  alan_ad?: string | null;
};

export type OdemeListesi = {
  kayitlar: OdemeKaydi[];
  toplam: number;
  sayfa: number;
  boyut: number;
  ozet: {
    toplam_tutar: string | null;
    adet: number;
    yontem_dagilimi: { yontem: OdemeYontemi; tutar: string | null; adet: number }[];
  };
};

export type BekleyenOdeme = {
  ogrenci_paketi_id: string;
  ogrenci: { id: string; ad: string; soyad: string };
  paket_adi: string;
  uygulanan_fiyat: string | null;
  atama_tarihi: string;
  bekleme_gun: number;
};

export type OdemeAl = { yontem: OdemeYontemi; tarih?: string; aciklama?: string };

export const odemeAl = (ogrenciPaketiId: string, g: OdemeAl) =>
  api<OgrenciPaketi>(`/api/ogrenci-paketleri/${ogrenciPaketiId}/odeme`, { method: "POST", body: JSON.stringify(g) });
export const odemeIptalEt = (odemeId: string, neden: string) =>
  api<unknown>(`/api/odemeler/${odemeId}/iptal`, { method: "POST", body: JSON.stringify({ neden }) });

export type OdemeSorgusu = {
  baslangic: string;
  bitis: string;
  yontem?: string;
  q?: string;
  sayfa: number;
  boyut: number;
  iptal_dahil: boolean;
};
export function odemeleriGetir(s: OdemeSorgusu) {
  const p = new URLSearchParams({ baslangic: s.baslangic, bitis: s.bitis, sayfa: String(s.sayfa), boyut: String(s.boyut), iptal_dahil: String(s.iptal_dahil) });
  if (s.yontem) p.set("yontem", s.yontem);
  if (s.q) p.set("q", s.q);
  return api<OdemeListesi>(`/api/odemeler?${p}`);
}
export const bekleyenOdemeleriGetir = () => api<BekleyenOdeme[]>("/api/odemeler/bekleyenler");
