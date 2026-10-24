// Erişim belirteci yalnızca bellekte tutulur (localStorage'a yazılmaz), böylece bir XSS
// açığı olsa bile kalıcı belirteç çalınamaz. Oturumu yenileme çerezi (httpOnly) taşır.
let erisimBelirteci: string | null = null;

export class ApiHata extends Error {
  durum: number;
  constructor(durum: number, mesaj: string) {
    super(mesaj);
    this.durum = durum;
  }
}

export function belirteciAyarla(belirtec: string | null) {
  erisimBelirteci = belirtec;
}

type BelirtecYaniti = { access_token: string };

async function mesajOku(yanit: Response): Promise<string> {
  try {
    const govde = await yanit.json();
    if (typeof govde.detail === "string") return govde.detail;
  } catch {
    /* gövde JSON değil */
  }
  return "Beklenmeyen bir hata oluştu.";
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

export async function api<T>(yol: string, secenekler: RequestInit = {}, yenidenDene = true): Promise<T> {
  const basliklar = new Headers(secenekler.headers);
  if (secenekler.body) basliklar.set("Content-Type", "application/json");
  if (erisimBelirteci) basliklar.set("Authorization", `Bearer ${erisimBelirteci}`);

  const yanit = await fetch(yol, { ...secenekler, headers: basliklar, credentials: "same-origin" });

  if (yanit.status === 401 && yenidenDene && !yol.startsWith("/api/auth/")) {
    if (await oturumuYenile()) return api<T>(yol, secenekler, false);
  }
  if (!yanit.ok) throw new ApiHata(yanit.status, await mesajOku(yanit));
  if (yanit.status === 204) return undefined as T;
  return (await yanit.json()) as T;
}
