import { api } from "../lib/api";

export type DenetimSatiri = {
  id: number;
  zaman: string;
  kullanici: { id: string; giris: string; ad_soyad?: string | null; rol: string } | null;
  islem: string;
  hedef_tur?: string | null;
  hedef_id?: string | null;
  ip?: string | null;
  detay?: Record<string, unknown> | null;
};

export type DenetimListesi = { items: DenetimSatiri[]; toplam: number; sayfa: number; boyut: number };

export type DenetimSorgusu = {
  islem?: string;
  baslangic?: string;
  bitis?: string;
  ara?: string;
  sayfa: number;
  boyut: number;
};

/** Bilinen işlem adlarının Türkçe karşılığı; bilinmeyen ad olduğu gibi gösterilir. */
export const ISLEM_ETIKET: Record<string, string> = {
  destek_bildirim_toplu_iptal: "Destek: bildirimler toplu iptal",
  destek_bildirim_toplu_yeniden_denendi: "Destek: bildirimler yeniden denendi",
  destek_hesap_aktife_alindi: "Destek: hesap aktif edildi",
  destek_hesap_pasife_alindi: "Destek: hesap pasife alındı",
  destek_kilit_acildi: "Destek: hesap kilidi açıldı",
  destek_oturumlar_kapatildi: "Destek: oturumlar kapatıldı",
  destek_sifre_sifirlandi: "Destek: şifre sıfırlandı",
  giris_basarili: "Giriş",
  giris_basarisiz: "Başarısız giriş",
  giris_sifre_dogru_ikili_bekliyor: "Şifre doğru, kod bekleniyor",
  ikili_dogrulama_basarisiz: "İki adımlı doğrulama başarısız",
  ikili_kurtarma_kodu_kullanildi: "Kurtarma kodu kullanıldı",
  ikili_kurulum_basladi: "İki adımlı doğrulama kurulumu başladı",
  ikili_kurulum_tamamlandi: "İki adımlı doğrulama kuruldu",
  sifre_degistirildi: "Şifre değiştirildi",
  sifre_degistirme_basarisiz: "Şifre değiştirme başarısız",
  profil_guncellendi: "Profil güncellendi",
  antrenor_olusturuldu: "Antrenör eklendi",
  antrenor_guncellendi: "Antrenör güncellendi",
  antrenor_sifre_sifirlandi: "Antrenör şifresi sıfırlandı",
  bildirim_tercihi_guncellendi: "Bildirim tercihi güncellendi",
  ders_hakki_duzeltildi: "Ders hakkı düzeltildi",
  grup_olusturuldu: "Grup oluşturuldu",
  grup_guncellendi: "Grup güncellendi",
  grup_programi_degisti: "Grup programı değişti",
  grup_ogrenci_eklendi: "Gruba öğrenci eklendi",
  grup_ogrenci_cikarildi: "Gruptan öğrenci çıkarıldı",
  kimlik_goruntulendi: "Kimlik görüntülendi",
  odeme_alindi: "Ödeme alındı",
  odeme_iptal_edildi: "Ödeme geri alındı",
  ogrenci_olusturuldu: "Öğrenci kaydı",
  ogrenci_guncellendi: "Öğrenci güncellendi",
  ogrenci_iletisim_degisti: "Öğrenci iletişim bilgisi değişti",
  ogrenci_foto_yuklendi: "Öğrenci fotoğrafı yüklendi",
  ogrenci_foto_silindi: "Öğrenci fotoğrafı silindi",
  ogrenci_paketi_atandi: "Paket atandı",
  ogrenci_paketi_iptal_edildi: "Paket iptal edildi",
  oturumlar_uretildi: "Dersler üretildi",
  paket_olusturuldu: "Paket oluşturuldu",
  paket_guncellendi: "Paket güncellendi",
  panel_hesabi_acildi: "Panel hesabı açıldı",
  panel_hesabi_ayrildi: "Panel hesabı ayrıldı",
  panel_hesabi_baglandi: "Panel hesabı bağlandı",
  panel_hesabi_sifre_sifirlandi: "Panel hesabı şifresi sıfırlandı",
  push_abonelik_kaydedildi: "Bildirim cihazı eklendi",
  push_abonelik_silindi: "Bildirim cihazı silindi",
  rapor_disa_aktarildi: "Rapor dışa aktarıldı",
  resit_gecisi: "Reşit geçişi",
  telefon_degisti: "Telefon değişti",
  telefon_degistirme_basarisiz: "Telefon değiştirme başarısız",
  telafi_iptal_edildi: "Telafi iptal edildi",
  telafi_planlandi: "Telafi planlandı",
  yenileme_yeniden_kullanim: "Yenileme yeniden kullanıldı",
  yoklama_alindi: "Yoklama alındı",
};

export const islemEtiketi = (islem: string) => ISLEM_ETIKET[islem] ?? islem;

export function denetimGetir(s: DenetimSorgusu) {
  const p = new URLSearchParams({ sayfa: String(s.sayfa), boyut: String(s.boyut) });
  if (s.islem) p.set("islem", s.islem);
  if (s.baslangic) p.set("baslangic", s.baslangic);
  if (s.bitis) p.set("bitis", s.bitis);
  if (s.ara) p.set("ara", s.ara);
  return api<DenetimListesi>(`/api/denetim?${p}`);
}
export const denetimIslemleriGetir = () => api<string[]>("/api/denetim/islemler");
