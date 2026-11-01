import { api } from "../lib/api";

export type DevamDersi = { tarih: string; durum: "geldi" | "gelmedi"; telafi_mi: boolean; grup_ad: string };
export type DevamOzeti = {
  katildi: number;
  gelmedi: number;
  oran: number | null;
  son30_katildi: number;
  son30_gelmedi: number;
  son30_oran: number | null;
  ard_arda_gelmedi: number;
  son_dersler: DevamDersi[];
};
export type DevamSatiri = { ogrenci_id: string; ad: string; soyad: string; devam: DevamOzeti };
export type GrupDevami = { grup_id: string; grup_ad: string; ogrenciler: DevamSatiri[] };

export const ogrenciDevamGetir = (id: string) => api<DevamOzeti>(`/api/ogrenciler/${id}/devam`);
export const grupDevamGetir = (id: string) => api<GrupDevami>(`/api/gruplar/${id}/devam`);
export const ogrencilerimGetir = () => api<GrupDevami[]>("/api/antrenor/ogrencilerim");
