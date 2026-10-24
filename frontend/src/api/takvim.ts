import { api } from "../lib/api";

export type OturumDurum = "planli" | "yapildi" | "iptal";
export type YoklamaDurum = "geldi" | "gelmedi";

export type OturumOzet = {
  id: string;
  tarih: string;
  baslangic: string;
  bitis: string;
  durum: OturumDurum;
  grup: { id: string; ad: string };
  antrenor: { id: string; ad_soyad: string } | null;
  ogrenci_sayisi: number;
  yoklama_alindi: boolean;
};

export type OturumOgrenci = {
  ogrenci_id: string;
  ad: string;
  soyad: string;
  foto_var: boolean;
  telafi_mi: boolean;
  yoklama: YoklamaDurum | null;
  bakiye: { normal: number; telafi: number };
};

export type OturumDetay = OturumOzet & { ogrenciler: OturumOgrenci[] };

export type YoklamaKaydi = { ogrenci_id: string; durum: YoklamaDurum };

const json = (g: unknown) => JSON.stringify(g);

export const oturumlariUret = (baslangic: string, bitis: string) =>
  api<{ olusturulan: number }>("/api/oturumlar/uret", { method: "POST", body: json({ baslangic, bitis }) });

export function takvimGetir(baslangic: string, bitis: string, antrenorId?: string) {
  const q = new URLSearchParams({ baslangic, bitis });
  if (antrenorId) q.set("antrenor_id", antrenorId);
  return api<OturumOzet[]>(`/api/takvim?${q.toString()}`);
}

export const oturumGetir = (id: string) => api<OturumDetay>(`/api/oturumlar/${id}`);

export const yoklamaKaydet = (id: string, kayitlar: YoklamaKaydi[]) =>
  api<OturumDetay>(`/api/oturumlar/${id}/yoklama`, { method: "PUT", body: json(kayitlar) });

export const telafiPlanla = (oturumId: string, ogrenciId: string) =>
  api<OturumDetay>(`/api/oturumlar/${oturumId}/telafi`, { method: "POST", body: json({ ogrenci_id: ogrenciId }) });
export const telafiGeriAl = (oturumId: string, ogrenciId: string) =>
  api<OturumDetay>(`/api/oturumlar/${oturumId}/telafi/${ogrenciId}`, { method: "DELETE" });
