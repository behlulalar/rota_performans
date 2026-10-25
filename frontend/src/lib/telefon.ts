// Telefon yardımcıları: arayüzde yalnız 10 haneli rakam dizisi tutulur, API'ye "+90" + 10 hane gider.

/** Girilen/yapıştırılan metni 10 haneli rakam dizisine indirger (baştaki 90 / 0 atılır). */
export function rakamlaraCevir(ham: string | null | undefined): string {
  let r = (ham ?? "").replace(/\D/g, "");
  if (r.length >= 12 && r.startsWith("90")) r = r.slice(2);
  else if (r.length >= 11 && r.startsWith("0")) r = r.slice(1);
  return r.slice(0, 10);
}

export const apiyeCevir = (rakamlar: string): string | null => (rakamlar ? "+90" + rakamlar : null);

export const gecerliMi = (rakamlar: string): boolean => /^\d{10}$/.test(rakamlar);

/** "+905321234567" -> "+90 532 123 45 67"; çözülemezse olduğu gibi döner. */
export function bicimle(apiDegeri: string | null | undefined): string {
  if (!apiDegeri) return "";
  const r = rakamlaraCevir(apiDegeri);
  if (!gecerliMi(r)) return apiDegeri;
  return `+90 ${r.slice(0, 3)} ${r.slice(3, 6)} ${r.slice(6, 8)} ${r.slice(8)}`;
}

export const TELEFON_HATA = "Telefon 10 haneli olmalı";

/** Şifre mesajı için numara: giriş bilgisi telefonsa o, değilse yedek (iletişim) telefonu. */
export function telefonSec(giris: string | null | undefined, yedek: string | null | undefined): string | null {
  if (giris && !giris.includes("@") && gecerliMi(rakamlaraCevir(giris))) return giris;
  return yedek && gecerliMi(rakamlaraCevir(yedek)) ? yedek : null;
}
