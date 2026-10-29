import { useCallback, useSyncExternalStore } from "react";

export type YaziBoyutu = "kucuk" | "normal" | "buyuk" | "cokbuyuk";

export const YAZI_BOYUTLARI: { deger: YaziBoyutu; ad: string; olcek: number }[] = [
  { deger: "kucuk", ad: "Küçük", olcek: 0.9 },
  { deger: "normal", ad: "Normal", olcek: 1 },
  { deger: "buyuk", ad: "Büyük", olcek: 1.1 },
  { deger: "cokbuyuk", ad: "Çok büyük", olcek: 1.25 },
];

const ANAHTAR = "rota-yazi-boyutu";
const dinleyiciler = new Set<() => void>();

function olcekBul(d: string | null | undefined): number {
  return YAZI_BOYUTLARI.find((b) => b.deger === d)?.olcek ?? 1;
}

/** Kayıtlı tercih; yoksa ya da geçersizse "normal". */
export function yaziBoyutuOku(): YaziBoyutu {
  try {
    const k = localStorage.getItem(ANAHTAR);
    if (YAZI_BOYUTLARI.some((b) => b.deger === k)) return k as YaziBoyutu;
  } catch {
    /* depolama kapalı olabilir */
  }
  return "normal";
}

/**
 * Ölçeği kök öğeye uygular (CSS `zoom`; arayüz sabit px kullandığı için rem ölçeklemesi işe yaramaz).
 * `--olcek` değişkeni, görünüm alanı birimlerini (dvh/vw) ölçeğe bölmek için de kullanılır.
 */
export function yaziBoyutuUygula(d: YaziBoyutu) {
  const kok = document.documentElement;
  kok.dataset.yaziBoyutu = d;
  kok.style.setProperty("--olcek", String(olcekBul(d)));
  dinleyiciler.forEach((fn) => fn());
}

export function yaziBoyutuKaydet(d: YaziBoyutu) {
  try {
    localStorage.setItem(ANAHTAR, d);
  } catch {
    /* tercih yalnızca bu oturumda geçerli olur */
  }
  yaziBoyutuUygula(d);
}

function abone(fn: () => void) {
  dinleyiciler.add(fn);
  return () => {
    dinleyiciler.delete(fn);
  };
}

function anlikOku(): YaziBoyutu {
  const d = document.documentElement.dataset.yaziBoyutu;
  return YAZI_BOYUTLARI.some((b) => b.deger === d) ? (d as YaziBoyutu) : "normal";
}

/** Geçerli yazı boyutu ve değiştirme işlevi. İlk değer index.html'deki betikten gelir. */
export function useYaziBoyutu() {
  const boyut = useSyncExternalStore(abone, anlikOku, () => "normal" as YaziBoyutu);
  const sec = useCallback((d: YaziBoyutu) => yaziBoyutuKaydet(d), []);
  return { boyut, sec };
}
