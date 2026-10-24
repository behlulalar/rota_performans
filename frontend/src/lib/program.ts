export const GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"];
const KISA = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

export const saat = (s: string) => s.slice(0, 5);

/**
 * Haftalık programı kısa yazar: aynı saatli günler birleşir ("Çar · Cum 17:30–19:00");
 * farklı saatli slotlar " · " ile ayrı yazılır ("Pzt 07:00–08:30 · Çar 17:30–19:00").
 */
export function programOzeti(p: { gun: number; baslangic: string; bitis: string }[]): string {
  if (p.length === 0) return "Program yok";
  const gruplar = new Map<string, number[]>();
  [...p]
    .sort((a, b) => a.gun - b.gun || a.baslangic.localeCompare(b.baslangic))
    .forEach((s) => {
      const anahtar = `${saat(s.baslangic)}–${saat(s.bitis)}`;
      gruplar.set(anahtar, [...(gruplar.get(anahtar) ?? []), s.gun]);
    });
  return [...gruplar.entries()]
    .map(([aralik, gunler]) => `${gunler.map((g) => KISA[g - 1]).join(" · ")} ${aralik}`)
    .join(" · ");
}

export function dakikaEkle(hhmm: string, dk: number): string | null {
  const m = /^(\d{2}):(\d{2})/.exec(hhmm);
  if (!m) return null;
  const t = Number(m[1]) * 60 + Number(m[2]) + dk;
  if (t >= 24 * 60) return null;
  return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
}
