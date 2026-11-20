import { api } from "../lib/api";
import type { OturumOzet } from "./takvim";

export type Durum = "aktif" | "pasif";
export type Cinsiyet = "kadin" | "erkek";
export type KimlikTur = "tc" | "pasaport";
export type IletisimRol = "anne" | "baba" | "diger" | "kendisi";
export type RizaTur = "aydinlatma" | "foto" | "whatsapp";

export type OgrenciOzet = {
  id: string;
  ad: string;
  soyad: string;
  dogum_tarihi: string;
  telefon: string | null;
  yas: number;
  durum: Durum;
  cinsiyet: Cinsiyet | null;
  kimlik_maskeli: string | null;
  foto_var: boolean;
  birincil_iletisim: { ad_soyad: string; telefon: string; rol: IletisimRol } | null;
};

export type IletisimKisisi = {
  id: string;
  rol: IletisimRol;
  ad_soyad: string;
  telefon: string;
  birincil: boolean;
  whatsapp_izni: boolean;
};

export type OgrenciDetay = OgrenciOzet & {
  anne_adi: string | null;
  baba_adi: string | null;
  kimlik_tur: KimlikTur;
  kayit_tarihi: string;
  iletisim_kisileri: IletisimKisisi[];
  rizalar: { tur: RizaTur; verildi: boolean; geri_cekildi: boolean }[];
  uyarilar: string[];
  gruplar: { id: string; ad: string }[];
  ders_hakki: { normal: number; telafi: number; kullanilabilir_telafi: number };
  hesap: { giris: string; rol: "veli" | "ogrenci"; aktif: boolean; bagli_ogrenci_sayisi: number } | null;
};

export type Liste = { kayitlar: OgrenciOzet[]; toplam: number; sayfa: number; boyut: number };

export type IletisimGirdi = { rol: IletisimRol; ad_soyad: string; telefon: string; birincil: boolean };

export type OgrenciTemel = {
  ad: string;
  soyad: string;
  anne_adi?: string | null;
  baba_adi?: string | null;
  dogum_tarihi: string;
  cinsiyet?: Cinsiyet | null;
  telefon?: string | null;
  kimlik_tur: KimlikTur;
  kimlik_no?: string | null;
};

export type OgrenciOlustur = OgrenciTemel & {
  iletisim_kisileri: IletisimGirdi[];
  rizalar: { aydinlatma: boolean; foto: boolean; whatsapp: boolean };
};

const json = (govde: unknown) => JSON.stringify(govde);

export function ogrencileriGetir(p: { q: string; durum: string; sayfa: number; boyut: number }) {
  const sorgu = new URLSearchParams({ sayfa: String(p.sayfa), boyut: String(p.boyut) });
  if (p.q) sorgu.set("q", p.q);
  if (p.durum) sorgu.set("durum", p.durum);
  return api<Liste>(`/api/ogrenciler?${sorgu}`);
}

export const ogrenciGetir = (id: string) => api<OgrenciDetay>(`/api/ogrenciler/${id}`);
export const ogrenciOlustur = (g: OgrenciOlustur) =>
  api<OgrenciDetay>("/api/ogrenciler", { method: "POST", body: json(g) });
export const ogrenciGuncelle = (id: string, g: Partial<OgrenciTemel>) =>
  api<OgrenciDetay>(`/api/ogrenciler/${id}`, { method: "PATCH", body: json(g) });
export const iletisimGuncelle = (id: string, kisiler: IletisimGirdi[]) =>
  api<OgrenciDetay>(`/api/ogrenciler/${id}/iletisim-kisileri`, { method: "PUT", body: json(kisiler) });
export const pasifeAl = (id: string) => api<OgrenciDetay>(`/api/ogrenciler/${id}/pasife-al`, { method: "POST" });
export const aktifEt = (id: string) => api<OgrenciDetay>(`/api/ogrenciler/${id}/aktif-et`, { method: "POST" });
export const kimlikGetir = (id: string) => api<{ kimlik_no: string }>(`/api/ogrenciler/${id}/kimlik`);

export function fotoYukle(id: string, dosya: Blob) {
  const form = new FormData();
  form.append("dosya", dosya, "foto.jpg");
  return api<void>(`/api/ogrenciler/${id}/foto`, { method: "POST", body: form });
}
export const fotoSil = (id: string) => api<void>(`/api/ogrenciler/${id}/foto`, { method: "DELETE" });

export type HesapAcYaniti = { giris: string; gecici_sifre: string | null; yeni_hesap: boolean };
export type ResitUyarisi = {
  id: string;
  ad: string;
  soyad: string;
  yas: number;
  birincil_rol: string | null;
  veli_hesabi_var: boolean;
  telefon: string | null;
};

export const hesapAc = (id: string, giris?: string) =>
  api<HesapAcYaniti>(`/api/ogrenciler/${id}/hesap`, { method: "POST", body: json(giris ? { giris } : {}) });
export const hesapKaldir = (id: string) => api<OgrenciDetay>(`/api/ogrenciler/${id}/hesap`, { method: "DELETE" });
export const hesapSifreSifirla = (id: string) =>
  api<{ gecici_sifre: string }>(`/api/ogrenciler/${id}/hesap/sifre-sifirla`, { method: "POST" });
export const resitUyarilariniGetir = () => api<ResitUyarisi[]>("/api/ogrenciler/resit-uyarilari");
export const resitGecisiYap = (id: string, g: { telefon: string; ad_soyad?: string }) =>
  api<OgrenciDetay>(`/api/ogrenciler/${id}/resit-gecisi`, { method: "POST", body: json(g) });

export type Sayac = "normal" | "telafi";
export type HakTur = "paket_yuklemesi" | "ders_kullanimi" | "devamsizlik" | "telafi_kullanimi" | "manuel_duzeltme" | "iptal" | "telafi_suresi_doldu";
export type HakHareketi = {
  id: string;
  zaman: string;
  sayac: Sayac;
  miktar: number;
  tur: HakTur;
  son_kullanma?: string | null;
  neden: string | null;
  oturum: { tarih: string; grup_ad: string } | null;
};
export type DersHakkiDefteri = { normal: number; telafi: number; hareketler: HakHareketi[] };
export type TelafiAdayi = { oturum: OturumOzet; bos_yer: number };
export type TelafiPlani = {
  oturum_id: string;
  tarih: string;
  baslangic: string;
  bitis: string;
  grup: { id: string; ad: string };
  yoklama: "geldi" | "gelmedi" | null;
};

export const dersHakkiGetir = (id: string) => api<DersHakkiDefteri>(`/api/ogrenciler/${id}/ders-hakki`);
export const dersHakkiDuzelt = (id: string, g: { sayac: Sayac; miktar: number; neden: string }) =>
  api<{ normal: number; telafi: number }>(`/api/ogrenciler/${id}/ders-hakki/duzeltme`, { method: "POST", body: json(g) });
export const telafiAdaylariGetir = (id: string, baslangic: string, bitis: string) =>
  api<TelafiAdayi[]>(`/api/ogrenciler/${id}/telafi-adaylari?${new URLSearchParams({ baslangic, bitis })}`);
export const telafiPlanlariGetir = (id: string) => api<TelafiPlani[]>(`/api/ogrenciler/${id}/telafi-planlari`);
