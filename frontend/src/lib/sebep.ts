import { rozetHata, rozetNotr, rozetUyari } from "./stil";

export type Sebep = "izinli" | "raporlu" | "yarisma" | "devamsiz";

export const SEBEPLER: { anahtar: Sebep; ad: string }[] = [
  { anahtar: "izinli", ad: "İzinli" },
  { anahtar: "raporlu", ad: "Raporlu" },
  { anahtar: "yarisma", ad: "Yarışma" },
  { anahtar: "devamsiz", ad: "Devamsız" },
];

export const SEBEP_AD: Record<Sebep, string> = { izinli: "İzinli", raporlu: "Raporlu", yarisma: "Yarışma", devamsiz: "Devamsız" };

/** Mazeretli sebepler telafi hakkı doğurur; Devamsız'da ders hakkı düşer. */
export const mazeretli = (s: Sebep) => s !== "devamsiz";

export const SEBEP_ACIKLAMA_MAKS = 500;

/** Rozet sınıfı: mazeretli sebepler nötr, Devamsız (habersiz) hata tonunda. */
export const sebepRozeti = (s: Sebep) => (s === "devamsiz" ? rozetHata : s === "yarisma" ? rozetNotr : rozetUyari);
