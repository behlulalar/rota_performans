import { api } from "../lib/api";

export type YoneticiOzet = {
  id: string;
  ad_soyad: string | null;
  giris: string;
  aktif: boolean;
  son_giris: string | null;
  olusturma: string;
  ben: boolean;
};

export type YoneticiOlusturYaniti = { yonetici: YoneticiOzet; gecici_sifre: string };

const json = (g: unknown) => JSON.stringify(g);

export const yoneticileriGetir = () => api<YoneticiOzet[]>("/api/yoneticiler");
export const yoneticiOlustur = (g: { ad_soyad: string; giris: string }) =>
  api<YoneticiOlusturYaniti>("/api/yoneticiler", { method: "POST", body: json(g) });
export const yoneticiGuncelle = (id: string, g: { ad_soyad?: string; giris?: string; aktif?: boolean }) =>
  api<YoneticiOzet>(`/api/yoneticiler/${id}`, { method: "PATCH", body: json(g) });
export const yoneticiSifreSifirla = (id: string) =>
  api<{ gecici_sifre: string }>(`/api/yoneticiler/${id}/sifre-sifirla`, { method: "POST" });
export const girisDegistir = (yeniGiris: string, sifre: string) =>
  api<{ giris: string }>("/api/auth/giris", { method: "PATCH", body: json({ yeni_giris: yeniGiris, sifre }) });
