import { api } from "../lib/api";

export type AntrenorOzet = {
  id: string;
  ad_soyad: string;
  telefon: string | null;
  aktif: boolean;
  giris: string | null;
  grup_sayisi: number;
};

export type AntrenorOlusturYaniti = { antrenor: AntrenorOzet; gecici_sifre: string };

const json = (g: unknown) => JSON.stringify(g);

export const antrenorleriGetir = (aktif?: boolean) =>
  api<AntrenorOzet[]>(`/api/antrenorler${aktif === undefined ? "" : `?aktif=${aktif}`}`);
export const antrenorOlustur = (g: { ad_soyad: string; telefon?: string; giris: string }) =>
  api<AntrenorOlusturYaniti>("/api/antrenorler", { method: "POST", body: json(g) });
export const antrenorGuncelle = (id: string, g: { ad_soyad?: string; telefon?: string; aktif?: boolean; giris?: string }) =>
  api<AntrenorOzet>(`/api/antrenorler/${id}`, { method: "PATCH", body: json(g) });
export const sifreSifirla = (id: string) =>
  api<{ gecici_sifre: string }>(`/api/antrenorler/${id}/sifre-sifirla`, { method: "POST" });
