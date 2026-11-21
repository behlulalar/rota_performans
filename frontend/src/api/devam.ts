import { api } from "../lib/api";
import type { Sebep } from "../lib/sebep";

export type DevamDersi = { tarih: string; durum: "geldi" | "gelmedi"; sebep: Sebep | null; aciklama?: string | null; telafi_mi: boolean; ek_ders_mi?: boolean; grup_ad: string };
export type GelmediSebepleri = Record<Sebep | "bilinmiyor", number>;
export type DevamOzeti = {
  katildi: number;
  gelmedi: number;
  gelmedi_sebepleri?: GelmediSebepleri;
  oran: number | null;
  son30_katildi: number;
  son30_gelmedi: number;
  son30_oran: number | null;
  ard_arda_gelmedi: number;
  son_dersler: DevamDersi[];
};
export type DevamSatiri = { ogrenci_id: string; ad: string; soyad: string; devam: DevamOzeti; telafi_bakiyesi?: number; telafi_planlanabilir?: number };
export type GrupDevami = { grup_id: string; grup_ad: string; ogrenciler: DevamSatiri[] };

export const ogrenciDevamGetir = (id: string) => api<DevamOzeti>(`/api/ogrenciler/${id}/devam`);
export const grupDevamGetir = (id: string) => api<GrupDevami>(`/api/gruplar/${id}/devam`);
export const ogrencilerimGetir = () => api<GrupDevami[]>("/api/antrenor/ogrencilerim");
