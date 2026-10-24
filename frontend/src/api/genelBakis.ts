import { api } from "../lib/api";

export type GrupDoluluk = {
  id: string;
  ad: string;
  ogrenci_sayisi: number;
  kontenjan: number;
  program: { gun: number; baslangic: string; bitis: string }[];
};

export type SonKayit = { id: string; ad: string; soyad: string; kayit_tarihi: string; foto_var: boolean };

export type GenelBakisVerisi = {
  ogrenci: { aktif: number; pasif: number; bu_ay_kayit: number };
  hesapsiz_aktif_ogrenci: number;
  grupsuz_aktif_ogrenci: number;
  gruplar: { aktif_grup: number; toplam_kontenjan: number; dolu: number; doluluk_listesi: GrupDoluluk[] };
  antrenor: { aktif: number };
  bekleyen_odeme: { adet: number; toplam_tutar: string };
  son_kayitlar: SonKayit[];
};

export const genelBakisiGetir = () => api<GenelBakisVerisi>("/api/genel-bakis");
