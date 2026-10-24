import type { ProgramSlot } from "../api/grup";

export const GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"];
const KISA = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

export const saat = (s: string) => s.slice(0, 5);

export function programOzeti(p: ProgramSlot[]): string {
  if (p.length === 0) return "Program yok";
  return [...p]
    .sort((a, b) => a.gun - b.gun || a.baslangic.localeCompare(b.baslangic))
    .map((s) => `${KISA[s.gun - 1]} ${saat(s.baslangic)}–${saat(s.bitis)}`)
    .join(", ");
}

export function dakikaEkle(hhmm: string, dk: number): string | null {
  const m = /^(\d{2}):(\d{2})/.exec(hhmm);
  if (!m) return null;
  const t = Number(m[1]) * 60 + Number(m[2]) + dk;
  if (t >= 24 * 60) return null;
  return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
}
