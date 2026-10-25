// Erişim belirteci yalnızca bellekte tutulur (localStorage'a yazılmaz), böylece bir XSS
// açığı olsa bile kalıcı belirteç çalınamaz. Oturumu yenileme çerezi (httpOnly) taşır.
let erisimBelirteci: string | null = null;

export type AlanHatasi = { alan: string; mesaj: string };

export class ApiHata extends Error {
  durum: number;
  alanlar: AlanHatasi[];
  constructor(durum: number, mesaj: string, alanlar: AlanHatasi[] = []) {
    super(mesaj);
    this.durum = durum;
    this.alanlar = alanlar;
  }
}

export function belirteciAyarla(belirtec: string | null) {
  erisimBelirteci = belirtec;
}

// Sunucu "şifre değiştirmelisin" (403 + X-Hata-Kodu) derse oturum durumu yenilensin diye
// AuthProvider kaydeder. Tek seferlik: yenileme sırasında tekrar tetiklenmez (döngü olmaz).
let sifreZorunluDinleyici: (() => void) | null = null;
let sifreZorunluBekliyor = false;

export function sifreZorunluDinleyiciAyarla(f: (() => void) | null) {
  sifreZorunluDinleyici = f;
}

type BelirtecYaniti = { access_token: string };

async function hataOku(yanit: Response): Promise<ApiHata> {
  try {
    const govde = await yanit.json();
    if (typeof govde.detail === "string") return new ApiHata(yanit.status, govde.detail);
    if (Array.isArray(govde.detail)) {
      const alanlar: AlanHatasi[] = govde.detail.map((d: { loc?: unknown[]; msg?: string }) => ({
        alan: Array.isArray(d.loc) ? d.loc.filter((x) => x !== "body").join(".") : "",
        mesaj: d.msg ?? "Geçersiz değer",
      }));
      const ozet = alanlar.map((x) => (x.alan ? `${x.alan}: ${x.mesaj}` : x.mesaj)).join(" • ");
      return new ApiHata(yanit.status, ozet || "Gönderilen bilgiler geçersiz.", alanlar);
    }
  } catch {
    /* gövde JSON değil */
  }
  return new ApiHata(yanit.status, "Beklenmeyen bir hata oluştu.");
}

// Aynı anda gelen birden çok 401 tek bir yenileme isteğini paylaşır.
let yenilemeSozu: Promise<boolean> | null = null;

export function oturumuYenile(): Promise<boolean> {
  yenilemeSozu ??= (async () => {
    try {
      const yanit = await fetch("/api/auth/refresh", { method: "POST", credentials: "same-origin" });
      if (!yanit.ok) {
        erisimBelirteci = null;
        return false;
      }
      erisimBelirteci = ((await yanit.json()) as BelirtecYaniti).access_token;
      return true;
    } finally {
      setTimeout(() => (yenilemeSozu = null), 0);
    }
  })();
  return yenilemeSozu;
}

async function istek(yol: string, secenekler: RequestInit, yenidenDene: boolean): Promise<Response> {
  const basliklar = new Headers(secenekler.headers);
  // FormData'da Content-Type'ı tarayıcı (sınır değeriyle birlikte) kendisi koyar.
  if (secenekler.body && !(secenekler.body instanceof FormData)) basliklar.set("Content-Type", "application/json");
  if (erisimBelirteci) basliklar.set("Authorization", `Bearer ${erisimBelirteci}`);

  const yanit = await fetch(yol, { ...secenekler, headers: basliklar, credentials: "same-origin" });

  if (yanit.status === 401 && yenidenDene && !yol.startsWith("/api/auth/")) {
    if (await oturumuYenile()) return istek(yol, secenekler, false);
  }
  if (
    yanit.status === 403 &&
    yanit.headers.get("X-Hata-Kodu") === "sifre_degistirmeli" &&
    sifreZorunluDinleyici &&
    !sifreZorunluBekliyor
  ) {
    sifreZorunluBekliyor = true;
    try {
      sifreZorunluDinleyici();
    } finally {
      setTimeout(() => (sifreZorunluBekliyor = false), 2000);
    }
  }
  if (!yanit.ok) throw await hataOku(yanit);
  return yanit;
}

export async function api<T>(yol: string, secenekler: RequestInit = {}): Promise<T> {
  const yanit = await istek(yol, secenekler, true);
  if (yanit.status === 204) return undefined as T;
  return (await yanit.json()) as T;
}

export async function apiBlob(yol: string, secenekler: RequestInit = {}): Promise<Blob> {
  return (await istek(yol, secenekler, true)).blob();
}
