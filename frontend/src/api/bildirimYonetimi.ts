import { api } from "../lib/api";

export type BildirimDurumu = "bekliyor" | "gonderildi" | "hata" | "iptal";
export type BildirimKanali = "push" | "whatsapp";
export type BildirimSablonu = "ders_gelmedi" | "ders_hakki_azaldi" | "ders_hakki_bitti" | "duyuru";

export const DURUM_ETIKET: Record<BildirimDurumu, string> = {
  bekliyor: "Bekliyor",
  gonderildi: "Gönderildi",
  hata: "Hatalı",
  iptal: "İptal",
};
export const KANAL_ETIKET: Record<BildirimKanali, string> = { push: "Uygulama", whatsapp: "WhatsApp" };
export const SABLON_ETIKET: Record<BildirimSablonu, string> = {
  ders_gelmedi: "Derse gelmedi",
  ders_hakki_azaldi: "Ders hakkı azaldı",
  ders_hakki_bitti: "Ders hakkı bitti",
  duyuru: "Duyuru",
};

export type DurumSayilari = Record<BildirimDurumu, number>;

export type BildirimOzeti = {
  son_7_gun: DurumSayilari;
  bugun: DurumSayilari;
  push_etkin: boolean;
  push_cihaz_sayisi: number;
  push_kullanici_sayisi: number;
  geciken_bekleyen: number;
};

export type BildirimKaydi = {
  id: number;
  olusturma: string;
  planli_zaman: string;
  gonderim_zamani: string | null;
  kanal: BildirimKanali;
  sablon: BildirimSablonu;
  sablon_etiket: string;
  durum: BildirimDurumu;
  deneme: number;
  hata: string | null;
  ogrenci: { id: string; ad: string; soyad: string };
  alici: { ad_soyad: string; rol: string };
  metin: string;
};

export type BildirimListesi = { kayitlar: BildirimKaydi[]; toplam: number; sayfa: number; boyut: number };

export type BildirimFiltre = { durum?: string; kanal?: string; sablon?: string; q?: string; sayfa: number; boyut: number };

const U = "/api/bildirim-yonetimi";

export const bildirimOzetiGetir = (kanal?: BildirimKanali) =>
  api<BildirimOzeti>(`${U}/ozet${kanal ? `?kanal=${kanal}` : ""}`);
export const bildirimleriGetir = (f: BildirimFiltre) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) if (v !== undefined && v !== "") p.set(k, String(v));
  return api<BildirimListesi>(`${U}?${p}`);
};
export const bildirimIptalEt = (id: number) => api<{ id: number; durum: BildirimDurumu }>(`${U}/${id}/iptal`, { method: "POST" });
export const bildirimYenidenDene = (id: number) =>
  api<{ id: number; durum: BildirimDurumu }>(`${U}/${id}/yeniden-dene`, { method: "POST" });
