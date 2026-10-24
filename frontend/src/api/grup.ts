import { api } from "../lib/api";

export type ProgramSlot = { id?: string; gun: number; baslangic: string; bitis: string };

export type GrupOzet = {
  id: string;
  ad: string;
  antrenor: { id: string; ad_soyad: string } | null;
  kontenjan: number;
  aktif: boolean;
  ogrenci_sayisi: number;
  program: ProgramSlot[];
};

export type GrupUye = {
  id: string;
  ad: string;
  soyad: string;
  yas: number;
  foto_var: boolean;
  katilim_baslangic: string;
};

export type GrupDetay = GrupOzet & { ogrenciler: GrupUye[] };

export type GrupOlustur = { ad: string; antrenor_id?: string | null; kontenjan: number; program: ProgramSlot[] };
export type GrupGuncelle = { ad?: string; antrenor_id?: string | null; kontenjan?: number; aktif?: boolean };

const json = (g: unknown) => JSON.stringify(g);

export const gruplariGetir = (aktif?: boolean) =>
  api<GrupOzet[]>(`/api/gruplar${aktif === undefined ? "" : `?aktif=${aktif}`}`);
export const grupGetir = (id: string) => api<GrupDetay>(`/api/gruplar/${id}`);
export const grupOlustur = (g: GrupOlustur) => api<GrupDetay>("/api/gruplar", { method: "POST", body: json(g) });
export const grupGuncelle = (id: string, g: GrupGuncelle) =>
  api<GrupDetay>(`/api/gruplar/${id}`, { method: "PATCH", body: json(g) });
export const programGuncelle = (id: string, p: ProgramSlot[]) =>
  api<GrupDetay>(`/api/gruplar/${id}/program`, { method: "PUT", body: json(p) });
export const ogrenciEkle = (id: string, ogrenci_id: string) =>
  api<GrupDetay>(`/api/gruplar/${id}/ogrenciler`, { method: "POST", body: json({ ogrenci_id }) });
export const ogrenciCikar = (id: string, ogrenci_id: string) =>
  api<GrupDetay>(`/api/gruplar/${id}/ogrenciler/${ogrenci_id}`, { method: "DELETE" });
