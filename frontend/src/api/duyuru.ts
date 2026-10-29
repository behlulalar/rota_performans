import { api } from "../lib/api";
import type { BildirimDurumu, BildirimKanali } from "./bildirimYonetimi";

export type HedefTuru = "oturum" | "grup" | "tum";
export type DuyuruHedefi = { tur: HedefTuru; oturum_id?: string; grup_idleri?: string[] };
export type DuyuruKanallari = { push: boolean; whatsapp: boolean };

export type KanalIstatistigi = { toplam: number; gonderildi: number; bekliyor: number; hata: number; iptal: number };
export type DuyuruIstatistik = { push: KanalIstatistigi; whatsapp: KanalIstatistigi };

export type DuyuruOzet = {
  id: string;
  baslik: string;
  metin: string;
  olusturma: string;
  hedef_tur: HedefTuru;
  hedef_ozet: string;
  oturum_id: string | null;
  kanallar: DuyuruKanallari;
  istatistik: DuyuruIstatistik;
};

export type DuyuruAlicisi = {
  bildirim_id: number;
  ogrenci_ad: string;
  alici_ad: string;
  kanal: BildirimKanali;
  durum: BildirimDurumu;
  hata: string | null;
  gonderim_zamani: string | null;
};

export type DuyuruDetayi = DuyuruOzet & { alicilar: DuyuruAlicisi[] };

export type Onizleme = { ogrenci: number; alici: number; push_alacak: number; push_yok: number; whatsapp_izinli: number };

export type DuyuruGonderimi = { baslik: string; metin: string; hedef: DuyuruHedefi; kanallar: DuyuruKanallari };

const U = "/api/duyurular";
const json = (g: unknown) => JSON.stringify(g);

export const duyurulariGetir = () => api<DuyuruOzet[]>(U);
export const duyuruGetir = (id: string) => api<DuyuruDetayi>(`${U}/${id}`);
export const duyuruOnizle = (hedef: DuyuruHedefi, kanallar: DuyuruKanallari) =>
  api<Onizleme>(`${U}/onizleme`, { method: "POST", body: json({ hedef, kanallar }) });
export const duyuruGonder = (g: DuyuruGonderimi) => api<DuyuruDetayi>(U, { method: "POST", body: json(g) });
