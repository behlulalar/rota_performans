/** "3400.00" | 3400 -> "3.400 ₺" (kuruş 0 ise gizlenir, değilse 2 hane). */
export function paraBicimle(deger: string | number | null | undefined): string {
  if (deger === null || deger === undefined || deger === "") return "—";
  const n = typeof deger === "number" ? deger : Number(deger);
  if (!Number.isFinite(n)) return "—";
  const tam = Math.round(n * 100) % 100 === 0;
  return `${n.toLocaleString("tr-TR", { minimumFractionDigits: tam ? 0 : 2, maximumFractionDigits: tam ? 0 : 2 })} ₺`;
}
