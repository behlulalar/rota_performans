/** Yerel saat dilimine göre YYYY-MM-DD (toISOString UTC kaydırması yapar, kullanılmaz). */
export function yyyyAyGun(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** YYYY-MM-DD metnini yerel gece yarısı olarak çözer. */
export function tarihCoz(s: string): Date {
  const [y, a, g] = s.split("-").map(Number);
  return new Date(y, a - 1, g);
}

export function gunEkle(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
}

/** Verilen günün haftasının Pazartesi'si. */
export function haftaBasi(d: Date): Date {
  const fark = (d.getDay() + 6) % 7;
  return gunEkle(d, -fark);
}

export const bugun = () => yyyyAyGun(new Date());

export const uzunTarih = (s: string) =>
  tarihCoz(s).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric", weekday: "long" });

export const kisaTarih = (d: Date) => d.toLocaleDateString("tr-TR", { day: "numeric", month: "long" });
