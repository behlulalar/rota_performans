import { api } from "../lib/api";
import type { Durum, Sayac, HakTur } from "./ogrenci";
import type { OdemeYontemi, PaketDurum } from "./paket";

export type VeliDers = {
  oturum_id: string;
  tarih: string;
  baslangic: string;
  bitis: string;
  grup_ad: string;
  telafi_mi: boolean;
  durum: "planli" | "yapildi" | "iptal";
  yoklama: "geldi" | "gelmedi" | null;
};

export type CocukOzet = {
  id: string;
  ad: string;
  soyad: string;
  foto_var: boolean;
  durum: Durum;
  gruplar: { id: string; ad: string }[];
  ders_hakki: { normal: number; telafi: number; kullanilabilir_telafi: number };
  siradaki_ders: VeliDers | null;
  odeme_bekleyen: number;
  ders_hakki_bitti: boolean;
};

export type VeliPaket = {
  id: string;
  paket_adi: string;
  ders_sayisi: number;
  uygulanan_fiyat: string;
  toplam_odenen: string;
  durum: PaketDurum;
  baslangic: string | null;
  bitis: string | null;
  olusturma: string;
  odemeler: { tarih: string; tutar: string; yontem: OdemeYontemi; iptal: boolean }[];
};

export type DersOzeti = {
  toplam: number;
  katildi: number;
  devamsiz: number;
  kalan: number;
  telafi_dogan: number;
  telafi_kullanilan: number;
  telafi_kalan: number;
};

export type CocukDetay = CocukOzet & {
  program: { grup_ad: string; gun: number; baslangic: string; bitis: string }[];
  yaklasan_dersler: VeliDers[];
  gecmis_dersler: VeliDers[];
  paketler: VeliPaket[];
  ders_ozeti: DersOzeti;
  hareketler: { zaman: string; sayac: Sayac; miktar: number; tur: HakTur }[];
};

export type Profil = { giris: string; rol: "veli" | "ogrenci"; ad_soyad: string | null; telefon: string | null };

export const cocuklarimiGetir = () => api<CocukOzet[]>("/api/benim/cocuklar");
export const cocukGetir = (id: string) => api<CocukDetay>(`/api/benim/cocuklar/${id}`);
export const profilGetir = () => api<Profil>("/api/benim/profil");
export const profilGuncelle = (g: { ad_soyad: string; telefon: string }) =>
  api<Profil>("/api/benim/profil", { method: "PATCH", body: JSON.stringify(g) });
export const sifreDegistir = (mevcut: string, yeni: string) =>
  api<void>("/api/auth/sifre-degistir", {
    method: "POST",
    body: JSON.stringify({ mevcut_sifre: mevcut, yeni_sifre: yeni }),
  });

export type BildirimTercihleri = { ders_gelmedi: boolean; ders_hakki: boolean; whatsapp: boolean; push: boolean };
export type BildirimTercihYaniti = BildirimTercihleri & { whatsapp_izni_var: boolean };

export const bildirimTercihleriGetir = () => api<BildirimTercihYaniti>("/api/benim/bildirim-tercihleri");
export const bildirimTercihleriKaydet = (g: BildirimTercihleri) =>
  api<BildirimTercihYaniti>("/api/benim/bildirim-tercihleri", { method: "PUT", body: JSON.stringify(g) });
