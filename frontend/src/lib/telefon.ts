// Telefon yardımcıları. Arayüzde bir numara "tam numara" dizisidir: "+" + ülke kodu + ulusal numara
// (ör. "+905321234567", yazılırken yarım olabilir: "+90532"). Boş dize "numara yok" demektir.
// API aynı kanonik biçimi kullanır. Türkiye (+90) için ulusal numara tam 10 hane, diğer ülkelerde
// ülke kodu dahil 8–15 hane (E.164) geçerlidir.

export type Ulke = { kod: string; iso: string; ad: string };

/** Ülke kodu seçicisindeki ülkeler; Türkiye ilk sırada ve varsayılandır. */
export const ULKELER: Ulke[] = [
  { kod: "90", iso: "TR", ad: "Türkiye / KKTC" },
  { kod: "49", iso: "DE", ad: "Almanya" },
  { kod: "31", iso: "NL", ad: "Hollanda" },
  { kod: "33", iso: "FR", ad: "Fransa" },
  { kod: "44", iso: "GB", ad: "Birleşik Krallık" },
  { kod: "32", iso: "BE", ad: "Belçika" },
  { kod: "43", iso: "AT", ad: "Avusturya" },
  { kod: "41", iso: "CH", ad: "İsviçre" },
  { kod: "39", iso: "IT", ad: "İtalya" },
  { kod: "34", iso: "ES", ad: "İspanya" },
  { kod: "30", iso: "GR", ad: "Yunanistan" },
  { kod: "359", iso: "BG", ad: "Bulgaristan" },
  { kod: "46", iso: "SE", ad: "İsveç" },
  { kod: "45", iso: "DK", ad: "Danimarka" },
  { kod: "47", iso: "NO", ad: "Norveç" },
  { kod: "48", iso: "PL", ad: "Polonya" },
  { kod: "40", iso: "RO", ad: "Romanya" },
  { kod: "381", iso: "RS", ad: "Sırbistan" },
  { kod: "387", iso: "BA", ad: "Bosna-Hersek" },
  { kod: "355", iso: "AL", ad: "Arnavutluk" },
  { kod: "389", iso: "MK", ad: "Kuzey Makedonya" },
  { kod: "357", iso: "CY", ad: "Kıbrıs (GKRY)" },
  { kod: "7", iso: "RU", ad: "Rusya / Kazakistan" },
  { kod: "380", iso: "UA", ad: "Ukrayna" },
  { kod: "994", iso: "AZ", ad: "Azerbaycan" },
  { kod: "995", iso: "GE", ad: "Gürcistan" },
  { kod: "374", iso: "AM", ad: "Ermenistan" },
  { kod: "966", iso: "SA", ad: "Suudi Arabistan" },
  { kod: "971", iso: "AE", ad: "BAE" },
  { kod: "974", iso: "QA", ad: "Katar" },
  { kod: "964", iso: "IQ", ad: "Irak" },
  { kod: "963", iso: "SY", ad: "Suriye" },
  { kod: "98", iso: "IR", ad: "İran" },
  { kod: "20", iso: "EG", ad: "Mısır" },
  { kod: "1", iso: "US", ad: "ABD / Kanada" },
];

export const VARSAYILAN_ULKE = "90";
const EN_FAZLA_HANE = 15;

const sadeRakam = (s: string) => s.replace(/\D/g, "");

/** "+4915123456789" -> { kod: "49", ulusal: "15123456789" }. Listede olmayan kod için ilk iki hane ülke kodu sayılır. */
export function ulkeAyir(tam: string | null | undefined): { kod: string; ulusal: string } {
  const r = sadeRakam(tam ?? "");
  if (!r) return { kod: VARSAYILAN_ULKE, ulusal: "" };
  const bulunan = [...ULKELER].sort((a, b) => b.kod.length - a.kod.length).find((u) => r.startsWith(u.kod));
  if (bulunan) return { kod: bulunan.kod, ulusal: r.slice(bulunan.kod.length) };
  return { kod: r.slice(0, 2), ulusal: r.slice(2) };
}

/** Ülke koduna göre ulusal numara için izin verilen en fazla hane. */
export const enFazlaUlusal = (kod: string) => (kod === "90" ? 10 : EN_FAZLA_HANE - kod.length);

/**
 * Girilen/yapıştırılan/API'den gelen metni tam numaraya çevirir. "+" ile başlıyorsa uluslararası okunur;
 * yoksa Türkiye biçimleri (5XX…, 05XX…, 905XX…) kabul edilir. Rakam yoksa boş dize döner.
 */
export function numaraCoz(ham: string | null | undefined): string {
  const metin = (ham ?? "").trim();
  let r = sadeRakam(metin);
  if (!r) return "";
  if (metin.startsWith("+")) {
    const { kod, ulusal } = ulkeAyir(r);
    return "+" + kod + ulusal.slice(0, enFazlaUlusal(kod));
  }
  if (r.length >= 12 && r.startsWith("90")) r = r.slice(2);
  else if (r.length >= 11 && r.startsWith("0")) r = r.slice(1);
  return "+90" + r.slice(0, 10);
}

/** API'ye gidecek değer; numara yoksa null. */
export const apiyeCevir = (tam: string): string | null => (tam ? tam : null);

export const gecerliMi = (tam: string): boolean => {
  if (!/^\+\d+$/.test(tam)) return false;
  const r = tam.slice(1);
  if (r.startsWith("0")) return false;
  return r.startsWith("90") ? r.length === 12 : r.length >= 8 && r.length <= EN_FAZLA_HANE;
};

/** "+905321234567" -> "+90 532 123 45 67"; yabancı: "+49 151 234 567 89"; çözülemezse olduğu gibi döner. */
export function bicimle(apiDegeri: string | null | undefined): string {
  if (!apiDegeri) return "";
  const tam = numaraCoz(apiDegeri);
  if (!gecerliMi(tam)) return apiDegeri;
  const { kod, ulusal } = ulkeAyir(tam);
  if (kod === "90") return `+90 ${ulusal.slice(0, 3)} ${ulusal.slice(3, 6)} ${ulusal.slice(6, 8)} ${ulusal.slice(8)}`;
  return `+${kod} ${ulusal.replace(/(\d{3})(?=\d)/g, "$1 ")}`;
}

/** Otomatik odak yalnızca fare/imleç olan cihazlarda: dokunmatik cihazda klavye ekranı kaydırıp sayfayı bozmasın. */
export const otomatikOdak = (): boolean => {
  try {
    return window.matchMedia("(pointer: fine)").matches;
  } catch {
    return false;
  }
};

export const TELEFON_HATA = "Geçerli bir telefon numarası girin (Türkiye için 10 hane)";

/** Şifre mesajı için numara: giriş bilgisi telefonsa o, değilse yedek (iletişim) telefonu. */
export function telefonSec(giris: string | null | undefined, yedek: string | null | undefined): string | null {
  if (giris && !giris.includes("@") && gecerliMi(numaraCoz(giris))) return giris;
  return yedek && gecerliMi(numaraCoz(yedek)) ? yedek : null;
}

/** "+905321234567" -> "https://wa.me/905321234567" (sohbeti doğrudan açar); geçersiz numarada null. */
export function whatsappAdresi(apiDegeri: string | null | undefined, metin?: string): string | null {
  const tam = numaraCoz(apiDegeri);
  if (!gecerliMi(tam)) return null;
  return `https://wa.me/${tam.slice(1)}${metin ? `?text=${encodeURIComponent(metin)}` : ""}`;
}
