import { deflateSync } from "node:zlib";
import { test as temel, expect, type APIResponse, type Page } from "@playwright/test";

export { expect };

export const YONETICI_GIRIS = process.env.E2E_ADMIN_GIRIS ?? "e2e.yonetici@example.com";
export const YONETICI_SIFRE = process.env.E2E_ADMIN_SIFRE ?? "e2e-yonetici-sifresi-123";

// window.confirm diyaloglarını her testte otomatik kabul eder.
export const test = temel.extend({
  page: async ({ page }, kullan) => {
    page.on("dialog", (d) => void d.accept());
    await kullan(page);
  },
});

let sayac = 0;
/** Testler arasında çakışmayan, zaman damgalı kısa kimlik (yalnız harf ve rakam). */
export function benzersiz(): string {
  sayac += 1;
  return `${Date.now().toString(36)}${sayac}${Math.floor(Math.random() * 1296).toString(36)}`;
}

/** 11 haneli T.C. kimlik algoritmasına uyan, rastgele ve benzersiz sahte numara. */
export function tcUret(): string {
  const d: number[] = [1 + Math.floor(Math.random() * 9)];
  for (let i = 1; i < 9; i++) d.push(Math.floor(Math.random() * 10));
  const tekler = d[0] + d[2] + d[4] + d[6] + d[8];
  const ciftler = d[1] + d[3] + d[5] + d[7];
  d.push((((tekler * 7 - ciftler) % 10) + 10) % 10);
  d.push(d.reduce((a, b) => a + b, 0) % 10);
  return d.join("");
}

/** Algoritmaya UYMAYAN (son hanesi bozulmuş) 11 haneli numara. */
export function gecersizTcUret(): string {
  const tc = tcUret();
  const son = (Number(tc[10]) + 1) % 10;
  return tc.slice(0, 10) + son;
}

/** Benzersiz sahte cep telefonu (düz rakam): 05XXXXXXXXX. */
export function telefonUret(): string {
  let s = "05";
  for (let i = 0; i < 9; i++) s += Math.floor(Math.random() * 10);
  return s;
}

/** 05551234567 -> "0555 123 45 67" (kullanıcının yazabileceği boşluklu biçim). */
export function telefonBosluklu(t: string): string {
  return `${t.slice(0, 4)} ${t.slice(4, 7)} ${t.slice(7, 9)} ${t.slice(9)}`;
}

/** Maskeleme kuralı: ilk 3 ve son 2 hane görünür. */
export function tcMaskeli(tc: string): string {
  return `${tc.slice(0, 3)}${"*".repeat(tc.length - 5)}${tc.slice(-2)}`;
}

function crc32(veri: Buffer): number {
  let c = ~0;
  for (const bayt of veri) {
    c ^= bayt;
    for (let i = 0; i < 8; i++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1));
  }
  return ~c >>> 0;
}

function pngParca(tur: string, veri: Buffer): Buffer {
  const uzunluk = Buffer.alloc(4);
  uzunluk.writeUInt32BE(veri.length);
  const govde = Buffer.concat([Buffer.from(tur, "ascii"), veri]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(govde));
  return Buffer.concat([uzunluk, govde, crc]);
}

/** Geçerli, küçük (16x16) düz renkli PNG üretir; fixture dosyası gerekmez. */
function pngUret(en = 16, boy = 16): Buffer {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(en, 0);
  ihdr.writeUInt32BE(boy, 4);
  ihdr[8] = 8; // bit derinliği
  ihdr[9] = 2; // RGB
  const satir = Buffer.concat([Buffer.from([0]), Buffer.alloc(en * 3, 0x3c)]);
  const ham = Buffer.concat(Array.from({ length: boy }, () => satir));
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    pngParca("IHDR", ihdr),
    pngParca("IDAT", deflateSync(ham)),
    pngParca("IEND", Buffer.alloc(0)),
  ]);
}

export const KUCUK_PNG = pngUret();

async function girisIstegi(page: Page, giris: string, sifre: string): Promise<APIResponse> {
  // Hız sınırına (429) takılırsa pencerenin dolmasını bekleyip yeniden dener.
  let yanit = await page.request.post("/api/auth/login", { data: { giris, sifre } });
  for (let i = 0; i < 3 && yanit.status() === 429; i++) {
    await page.waitForTimeout(20_000);
    yanit = await page.request.post("/api/auth/login", { data: { giris, sifre } });
  }
  return yanit;
}

/**
 * API ile yönetici girişi yapar. Yenileme çerezi sayfanın bağlamına yazılır, yani sonraki
 * page.goto() oturumlu açılır; dönen erişim belirteci doğrudan API çağrıları içindir.
 */
export async function yoneticiApiGirisi(page: Page): Promise<string> {
  const yanit = await girisIstegi(page, YONETICI_GIRIS, YONETICI_SIFRE);
  expect(yanit.ok(), `Yönetici girişi başarısız: ${yanit.status()}`).toBeTruthy();
  return ((await yanit.json()) as { access_token: string }).access_token;
}

/** Arayüzden giriş formunu doldurur. */
export async function arayuzdenGiris(page: Page, giris: string, sifre: string): Promise<void> {
  await page.goto("/giris");
  await page.getByLabel("Telefon veya e-posta").fill(giris);
  await page.getByLabel("Şifre", { exact: true }).fill(sifre);
  await page.getByRole("button", { name: "Giriş yap" }).click();
}

export type SahteOgrenci = { id: string; ad: string; soyad: string; telefon: string; tc: string };

/** API ile hızlıca öğrenci oluşturur (benzersiz ad, TC ve telefon). */
export async function ogrenciOlusturAPI(page: Page, token: string, onek = "Api"): Promise<SahteOgrenci> {
  const k = benzersiz();
  const ad = `${onek}${k}`;
  const soyad = `Ogrenci${k}`;
  const telefon = telefonUret();
  const tc = tcUret();
  const yanit = await page.request.post("/api/ogrenciler", {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      ad,
      soyad,
      dogum_tarihi: "2015-05-10",
      kimlik_tur: "tc",
      kimlik_no: tc,
      iletisim_kisileri: [{ rol: "diger", ad_soyad: `Veli ${k}`, telefon, birincil: true }],
      rizalar: { aydinlatma: true, foto: false, whatsapp: false },
    },
  });
  expect(yanit.status(), await yanit.text()).toBe(201);
  const govde = (await yanit.json()) as { id: string };
  return { id: govde.id, ad, soyad, telefon, tc };
}
