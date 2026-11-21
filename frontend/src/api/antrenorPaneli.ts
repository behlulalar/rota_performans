import { api } from "../lib/api";
import type { TelafiPlani } from "./ogrenci";
import type { OturumDurum } from "./takvim";

export type YoklamaDurumu = "bekliyor" | "alindi" | "eksik" | "iptal";

export type BugunDers = {
  id: string;
  tarih: string;
  grup: { id: string; ad: string };
  baslangic: string;
  bitis: string;
  durum: OturumDurum;
  beklenen_ogrenci: number;
  yoklama_alinan: number;
  yoklama_durumu: YoklamaDurumu;
  yoklama_acik: boolean;
  telafi_sayisi: number;
  ek_ders_sayisi?: number;
};

export type BugunYaniti = {
  tarih: string;
  dersler: BugunDers[];
  siradaki: string | null;
  ozet: { ders_sayisi: number; toplam_ogrenci: number; yoklama_bekleyen: number };
  eksik_yoklamalar: BugunDers[];
};

export type AntrenorProfil = { id: string; foto_var: boolean; ad_soyad: string; telefon: string | null; giris: string };

export const bugunGetir = () => api<BugunYaniti>("/api/antrenor/bugun");
export const antrenorProfilGetir = () => api<AntrenorProfil>("/api/antrenor/profil");
export const antrenorProfilGuncelle = (g: { ad_soyad: string }) =>
  api<AntrenorProfil>("/api/antrenor/profil", { method: "PATCH", body: JSON.stringify(g) });

export type AntrenorOgrenciTelafi = { kullanilabilir: number; son_kullanma: string | null; planlar: TelafiPlani[] };
export const antrenorOgrenciTelafiGetir = (ogrenciId: string) => api<AntrenorOgrenciTelafi>(`/api/antrenor/ogrenciler/${ogrenciId}/telafi`);
