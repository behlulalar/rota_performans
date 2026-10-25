import { api } from "../lib/api";

export type PaketTur = "aylik" | "uc_aylik" | "alti_aylik" | "yillik" | "ozel_ders";
export type PaketDurum = "odeme_bekliyor" | "odendi" | "iptal";

export type Paket = {
  id: string;
  ad: string;
  tur: PaketTur;
  ders_sayisi: number;
  sure_ay: number;
  varsayilan_fiyat: string;
  aktif: boolean;
};

export type PaketOlustur = {
  ad: string;
  tur: PaketTur;
  ders_sayisi: number;
  sure_ay: number;
  varsayilan_fiyat: string;
};

export type OgrenciPaketi = {
  id: string;
  paket_adi: string;
  ders_sayisi: number;
  liste_fiyati: string;
  uygulanan_fiyat: string;
  fiyat_ozel_mi: boolean;
  durum: PaketDurum;
  baslangic: string | null;
  bitis: string | null;
  toplam_odenen: string;
  olusturma: string;
  odemeler?: OdemeSatiri[];
};

export type OdemeYontemi = "nakit" | "havale_eft" | "diger";
export type OdemeSatiri = {
  id: string;
  tutar: string;
  tarih: string;
  yontem: OdemeYontemi;
  aciklama?: string | null;
  iptal: boolean;
  iptal_nedeni?: string | null;
  alan_ad?: string | null;
};

export type PaketAtama = {
  paket_id: string;
  baslangic?: string;
  ozel_fiyat?: string;
  ozel_fiyat_nedeni?: string;
};

export const TUR_ETIKET: Record<PaketTur, string> = {
  aylik: "Aylık",
  uc_aylik: "3 aylık",
  alti_aylik: "6 aylık",
  yillik: "Yıllık",
  ozel_ders: "Özel ders",
};

export const DURUM_ETIKET: Record<PaketDurum, string> = {
  odeme_bekliyor: "Ödeme bekliyor",
  odendi: "Ödendi",
  iptal: "İptal",
};

const json = (govde: unknown) => JSON.stringify(govde);

export const paketleriGetir = () => api<Paket[]>("/api/paketler");
export const paketOlustur = (g: PaketOlustur) => api<Paket>("/api/paketler", { method: "POST", body: json(g) });
export const paketGuncelle = (id: string, g: { ad?: string; varsayilan_fiyat?: string; aktif?: boolean }) =>
  api<Paket>(`/api/paketler/${id}`, { method: "PATCH", body: json(g) });

export const ogrenciPaketleriniGetir = (ogrenciId: string) => api<OgrenciPaketi[]>(`/api/ogrenciler/${ogrenciId}/paketler`);
export const paketAta = (ogrenciId: string, g: PaketAtama) =>
  api<OgrenciPaketi>(`/api/ogrenciler/${ogrenciId}/paketler`, { method: "POST", body: json(g) });
export const ogrenciPaketiniIptalEt = (id: string) =>
  api<OgrenciPaketi>(`/api/ogrenci-paketleri/${id}/iptal`, { method: "POST" });
