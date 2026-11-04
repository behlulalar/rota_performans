import { api } from "../lib/api";
import type { OdemeYontemi } from "./odeme";

export type ManuelKayitTuru = "gelir" | "gider";
export type ManuelKayit = {
  id: string;
  tur: ManuelKayitTuru;
  tutar: string | null;
  tarih: string;
  yontem: OdemeYontemi;
  aciklama: string;
  olusturan: string | null;
  olusturma: string;
  iptal: boolean;
  iptal_nedeni: string | null;
};
export type ManuelKayitGirdi = Pick<ManuelKayit, "tur" | "tarih" | "yontem" | "aciklama"> & { tutar: string };

export const manuelKayitlariGetir = (baslangic: string, bitis: string) =>
  api<ManuelKayit[]>(`/api/manuel-kayitlar?${new URLSearchParams({ baslangic, bitis })}`);
export const manuelKayitEkle = (g: ManuelKayitGirdi) =>
  api<ManuelKayit>("/api/manuel-kayitlar", { method: "POST", body: JSON.stringify(g) });
export const manuelKayitIptal = (id: string, neden: string) =>
  api<ManuelKayit>(`/api/manuel-kayitlar/${id}/iptal`, { method: "POST", body: JSON.stringify({ neden }) });
