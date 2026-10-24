export function tcGecerli(no: string): boolean {
  if (!/^[1-9]\d{10}$/.test(no)) return false;
  const d = no.split("").map(Number);
  const tekler = d[0] + d[2] + d[4] + d[6] + d[8];
  const ciftler = d[1] + d[3] + d[5] + d[7];
  const d10 = (((tekler * 7 - ciftler) % 10) + 10) % 10;
  const d11 = d.slice(0, 10).reduce((a, b) => a + b, 0) % 10;
  return d[9] === d10 && d[10] === d11;
}

export function yasHesapla(dogum: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dogum);
  if (!m) return null;
  const bugun = new Date();
  let yas = bugun.getFullYear() - Number(m[1]);
  const once = bugun.getMonth() + 1 < Number(m[2]) || (bugun.getMonth() + 1 === Number(m[2]) && bugun.getDate() < Number(m[3]));
  if (once) yas--;
  return yas;
}

export const ROL_ETIKET = { anne: "Anne", baba: "Baba", diger: "Diğer", kendisi: "Kendisi" } as const;

export function tarihBicimle(iso: string): string {
  const [y, a, g] = iso.slice(0, 10).split("-");
  return `${g}.${a}.${y}`;
}

export function hataMesaji(err: unknown): string {
  return err instanceof Error ? err.message : "Bağlantı kurulamadı. Lütfen tekrar deneyin.";
}
