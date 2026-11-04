// Ortak sınıf dizeleri: tüm sayfalar aynı görünümü paylaşsın.
export const dugme =
  "inline-flex items-center justify-center rounded-[10px] border border-cizgi-guclu bg-yuzey px-4 min-h-11 text-[13px] font-medium text-metin hover:border-altin hover:text-altin-metin disabled:opacity-50 disabled:cursor-not-allowed transition-colors";
export const birincilDugme =
  "inline-flex items-center justify-center rounded-[10px] border border-birincil bg-birincil text-birincil-metin font-medium px-5 min-h-11 text-[13px] hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity";
export const girdi =
  "mt-1 w-full rounded-[10px] bg-zemin border border-cizgi-guclu px-3 min-h-11 py-1.5 text-sm outline-none focus:border-altin";
export const secimKutusu =
  "rounded-[10px] bg-yuzey border border-cizgi-guclu px-3 min-h-11 text-sm outline-none focus:border-altin";
export const bilgiKutusu = "rounded-[10px] border border-altin/50 bg-altin/10 text-altin-metin text-[13px] px-3 py-2";
export const tehlikeKutusu = "rounded-[10px] border-2 border-hata bg-hata-zemin text-hata text-sm font-semibold px-3 py-2.5";
export const uyariKutusu = "rounded-[10px] border border-uyari/40 bg-uyari-zemin text-uyari text-[13px] px-3 py-2";
export const hataKutusu = "rounded-[10px] border border-hata/40 bg-hata-zemin text-hata text-[13px] px-3 py-2";
export const basariKutusu = "rounded-[10px] border border-basari/40 bg-basari-zemin text-basari text-[13px] px-3 py-2";

// Rozetler yuvarlak ve dolgu zeminlidir.
const rozet = "inline-block rounded-full px-2.5 py-0.5 text-[11px] font-medium leading-4 whitespace-nowrap";
export const rozetBasari = `${rozet} bg-basari-zemin text-basari`;
export const rozetUyari = `${rozet} bg-uyari-zemin text-uyari`;
export const rozetHata = `${rozet} bg-hata-zemin text-hata`;
export const rozetNotr = `${rozet} bg-yuzey-yuksek text-metin-soluk`;
export const rozetBirincil = `${rozet} bg-altin/15 text-altin-metin`;

// Tablo ve liste satırları: ince çizgili, en az 52px
export const th = "px-4 h-10 text-left text-[11px] font-semibold uppercase tracking-[0.12em] text-metin-soluk";
export const td = "px-4 h-[52px]";
export const satir = "border-t border-cizgi hover:bg-yuzey-yuksek";
export const listeSatiri = "border-t border-cizgi first:border-t-0 min-h-[52px]";

// Serif başlık sınıfı (sayfa, kart ve özet değerleri)
export const baslikYazi = "font-display font-medium";
// Kart kenarı
export const kartKutusu = "bg-yuzey border border-cizgi rounded-[14px]";
