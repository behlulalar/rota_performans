import { api } from "../lib/api";

export type KurulumBilgisi = { gizli_anahtar: string; otpauth_uri: string };
export type KurulumSonucu = { access_token: string; kurtarma_kodlari: string[] };

const json = (g: unknown) => JSON.stringify(g);

export const ikiAdimKurulumu = (bekleyen_belirtec: string) =>
  api<KurulumBilgisi>("/api/auth/2fa/kurulum", { method: "POST", body: json({ bekleyen_belirtec }) });
export const ikiAdimKurulumuDogrula = (bekleyen_belirtec: string, kod: string) =>
  api<KurulumSonucu>("/api/auth/2fa/kurulum-dogrula", { method: "POST", body: json({ bekleyen_belirtec, kod }) });
export const ikiAdimDogrula = (bekleyen_belirtec: string, kod: string) =>
  api<{ access_token: string }>("/api/auth/2fa/dogrula", { method: "POST", body: json({ bekleyen_belirtec, kod }) });
