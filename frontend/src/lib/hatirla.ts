import { bicimle, gecerliMi, numaraCoz } from "./telefon";
import type { Panel } from "./panel";

// "Beni hatırla" tercihi ve hatırlanan hesap (yalnızca giriş bilgisi ve görünen ad; şifre asla saklanmaz).
const HATIRLA_ANAHTARI = "rota-hatirla";
const TERCIH_ANAHTARI = "rota-hatirla-tercih";

export type HatirlananHesap = { giris: string; ad: string; panel?: Panel };

export function hatirlananiOku(): HatirlananHesap | null {
  try {
    const ham = localStorage.getItem(HATIRLA_ANAHTARI);
    if (!ham) return null;
    const v = JSON.parse(ham) as Partial<HatirlananHesap>;
    const panel = v.panel === "veli" || v.panel === "antrenor" || v.panel === "yonetici" || v.panel === "destek" ? v.panel : undefined;
    return typeof v.giris === "string" && v.giris
      ? { giris: v.giris, ad: typeof v.ad === "string" && v.ad ? v.ad : v.giris, panel }
      : null;
  } catch {
    return null;
  }
}

export function hatirlananiKaydet(hesap: HatirlananHesap): void {
  try {
    localStorage.setItem(HATIRLA_ANAHTARI, JSON.stringify(hesap));
    localStorage.setItem(TERCIH_ANAHTARI, "1");
  } catch {
    /* depolama kapalı */
  }
}

export function hatirlananiSil(): void {
  try {
    localStorage.removeItem(HATIRLA_ANAHTARI);
    localStorage.removeItem(TERCIH_ANAHTARI);
  } catch {
    /* depolama kapalı */
  }
}

// Kullanıcı kendisi çıkış yaptıysa giriş ekranında "oturum süreniz doldu" uyarısı gösterilmez.
const CIKIS_ANAHTARI = "rota-cikis-yapildi";

export function cikisIsaretle(yapildi: boolean): void {
  try {
    if (yapildi) localStorage.setItem(CIKIS_ANAHTARI, "1");
    else localStorage.removeItem(CIKIS_ANAHTARI);
  } catch {
    /* depolama kapalı */
  }
}

export function cikisYapildiMi(): boolean {
  try {
    return localStorage.getItem(CIKIS_ANAHTARI) === "1";
  } catch {
    return false;
  }
}

function uygulamaYuklu(): boolean {
  try {
    return (
      window.matchMedia("(display-mode: standalone)").matches ||
      (navigator as Navigator & { standalone?: boolean }).standalone === true
    );
  } catch {
    return false;
  }
}

/** Kayıtlı tercih varsa o; yoksa uygulama yüklü modda işaretli, değilse işaretsiz. */
export function varsayilanHatirla(): boolean {
  try {
    if (localStorage.getItem(TERCIH_ANAHTARI) === "1") return true;
  } catch {
    /* depolama kapalı */
  }
  return uygulamaYuklu();
}

/** "+905551112233" / "05551112233" -> "+90 555 111 22 33"; çözülemeyen (ör. eski e-posta girişi) olduğu gibi kalır. */
export function girisiBicimle(giris: string): string {
  const tam = numaraCoz(giris);
  return !giris.includes("@") && gecerliMi(tam) ? bicimle(tam) : giris;
}
