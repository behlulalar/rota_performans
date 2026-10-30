import { api } from "../lib/api";
import type { BildirimDurumu, BildirimKanali } from "./bildirimYonetimi";

export type Ping = { ok: boolean; gecikme_ms: number | null };
export type KuyrukSayilari = Record<BildirimDurumu, number> & { geciken_bekleyen: number };
export type SistemDurumu = {
  ortam: string;
  surum: string;
  veritabani: Ping;
  redis: Ping;
  isci: { canli: boolean; son_atis: string | null; saniye_once: number | null };
  bildirim_kuyrugu: KuyrukSayilari;
  push_yapilandirildi: boolean;
  whatsapp_yapilandirildi: boolean;
};

export type HesapRolu = "admin" | "destek" | "antrenor" | "veli" | "ogrenci";
export const ROL_ETIKET: Record<HesapRolu, string> = {
  admin: "Yönetici",
  destek: "Teknik destek",
  antrenor: "Antrenör",
  veli: "Veli",
  ogrenci: "Öğrenci",
};

export type HesapSatiri = {
  id: string;
  giris: string;
  ad_soyad: string | null;
  rol: HesapRolu;
  aktif: boolean;
  kilitli: boolean;
  kilit_bitis: string | null;
  son_giris: string | null;
  olusturma: string;
  sifre_degistirmeli: boolean;
  totp_aktif: boolean;
  ben: boolean;
};
export type HesapListesi = { kayitlar: HesapSatiri[]; toplam: number; sayfa: number; boyut: number };
export type OturumSatiri = { id: string; olusturma: string; bitis: string; hatirla: boolean; aktif: boolean };

export type DestekBildirimSatiri = {
  id: number;
  olusturma: string;
  planli_zaman: string;
  gonderim_zamani: string | null;
  kanal: BildirimKanali;
  sablon: string;
  durum: BildirimDurumu;
  deneme: number;
  hata: string | null;
  parametreler: Record<string, unknown> | null;
  ogrenci_id: string;
  alici_iletisim_id: string;
  yoklama_id: string | null;
  duyuru_id: string | null;
  metin: string;
};
export type DestekBildirimListesi = { kayitlar: DestekBildirimSatiri[]; toplam: number; sayfa: number; boyut: number };
export type TopluSonuc = { islenen: number; atlanan: number };

const U = "/api/destek";
const json = (g: unknown) => JSON.stringify(g);

export const sistemDurumuGetir = () => api<SistemDurumu>(`${U}/sistem-durumu`);

export function hesaplariGetir(f: { q?: string; rol?: string; sayfa: number; boyut: number }) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) if (v !== undefined && v !== "") p.set(k, String(v));
  return api<HesapListesi>(`${U}/hesaplar?${p}`);
}
export const kilidiAc = (id: string) => api<HesapSatiri>(`${U}/hesaplar/${id}/kilit-ac`, { method: "POST" });
export const hesapSifreSifirla = (id: string) =>
  api<{ gecici_sifre: string }>(`${U}/hesaplar/${id}/sifre-sifirla`, { method: "POST" });
export const hesabiPasifeAl = (id: string) => api<HesapSatiri>(`${U}/hesaplar/${id}/pasif`, { method: "POST" });
export const hesabiAktifeAl = (id: string) => api<HesapSatiri>(`${U}/hesaplar/${id}/aktif`, { method: "POST" });
export const oturumlariGetir = (id: string) => api<OturumSatiri[]>(`${U}/hesaplar/${id}/oturumlar`);
export const oturumlariKapat = (id: string) =>
  api<{ kapatilan: number }>(`${U}/hesaplar/${id}/oturumlari-kapat`, { method: "POST" });

export function destekBildirimleriGetir(f: { durum?: string; kanal?: string; sayfa: number; boyut: number }) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) if (v !== undefined && v !== "") p.set(k, String(v));
  return api<DestekBildirimListesi>(`${U}/bildirimler?${p}`);
}
export const topluYenidenDene = (g: { ids?: number[]; tum_hatalilar?: boolean }) =>
  api<TopluSonuc>(`${U}/bildirimler/toplu-yeniden-dene`, { method: "POST", body: json(g) });
export const topluIptal = (g: { ids?: number[]; tum_hatalilar?: boolean }) =>
  api<TopluSonuc>(`${U}/bildirimler/toplu-iptal`, { method: "POST", body: json(g) });
