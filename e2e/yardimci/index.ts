import { deflateSync } from "node:zlib";
import { test as temel, expect, type APIResponse, type Page } from "@playwright/test";

export { expect };

export const YONETICI_GIRIS = process.env.E2E_ADMIN_GIRIS ?? "e2e.yonetici@example.com";
export const YONETICI_SIFRE = process.env.E2E_ADMIN_SIFRE ?? "e2e-yonetici-sifresi-123";

// Uygulamanın onay penceresini (OnayPenceresi) her testte otomatik onaylar.
export const test = temel.extend({
  page: async ({ page }, kullan) => {
    await page.addLocatorHandler(page.locator("[data-onay-penceresi]"), async (pencere) => {
      await pencere.getByRole("button").last().click();
    });
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

/** Arayüzdeki telefon kutusuna yazılacak 10 hane (+90 öneki kutuda sabittir): 5XXXXXXXXX. */
export function telefonUret10(): string {
  return telefonUret().slice(1);
}

/** "+905551234567" -> "0555 123 45 67" (kullanıcının giriş ekranında yazabileceği boşluklu biçim). */
export function telefonBosluklu(t: string): string {
  const r = t.replace(/\D/g, "").slice(-10);
  return `0${r.slice(0, 3)} ${r.slice(3, 6)} ${r.slice(6, 8)} ${r.slice(8)}`;
}

/** "+905551234567" -> "+90 555 123 45 67" (arayüzde görünen biçim). */
export function telefonGorunen(t: string): string {
  const r = t.replace(/\D/g, "").slice(-10);
  return `+90 ${r.slice(0, 3)} ${r.slice(3, 6)} ${r.slice(6, 8)} ${r.slice(8)}`;
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

export type Panel = "veli" | "antrenor" | "yonetici";
const PANEL_YOLU: Record<Panel, string> = { veli: "/giris", antrenor: "/antrenor-giris", yonetici: "/yonetici-giris" };

/** Giriş bilgisinden panel çıkarılır: e2e yöneticisi, "antrenor." ile başlayanlar antrenör, kalanı veli. */
function panelBul(giris: string): Panel {
  if (giris === YONETICI_GIRIS) return "yonetici";
  return giris.startsWith("antrenor.") ? "antrenor" : "veli";
}

/** Arayüzden giriş formunu doldurur. Panel verilmezse giriş bilgisinden bulunur. */
export async function arayuzdenGiris(page: Page, giris: string, sifre: string, panel: Panel = panelBul(giris)): Promise<void> {
  await page.goto(PANEL_YOLU[panel]);
  await page.getByLabel("Telefon veya e-posta").fill(giris);
  await page.getByLabel("Şifre", { exact: true }).fill(sifre);
  await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
  // Giriş hız sınırına (IP başına dakikada 20) takılırsa pencere dolunca yeniden dener.
  const sinir = page.getByRole("alert").filter({ hasText: "Çok fazla deneme" });
  for (let i = 0; i < 3; i++) {
    if (!(await sinir.waitFor({ state: "visible", timeout: 2000 }).then(() => true, () => false))) break;
    await page.waitForTimeout(20_000);
    await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
  }
}

export const YENI_SIFRE = "yeni-sifre-12345";

/** Geçici şifreyle girişte açılan zorunlu ekranda yeni şifreyi belirler (UI). */
export async function zorunluSifreyiBelirle(page: Page, gecici: string, yeni: string = YENI_SIFRE): Promise<void> {
  await expect(page.getByRole("heading", { name: "Şifrenizi belirleyin" })).toBeVisible();
  await page.getByLabel("Mevcut (geçici) şifre").fill(gecici);
  await page.getByLabel("Yeni şifre", { exact: true }).fill(yeni);
  await page.getByLabel("Yeni şifre (tekrar)").fill(yeni);
  await page.getByRole("button", { name: "Şifreyi kaydet" }).click();
}

/** Arayüzden geçici şifreyle girer ve zorunlu ekranda yeni şifre belirler. */
export async function geciciSifreyleGiris(page: Page, giris: string, gecici: string, yeni: string = YENI_SIFRE): Promise<string> {
  await arayuzdenGiris(page, giris, gecici);
  await zorunluSifreyiBelirle(page, gecici, yeni);
  return yeni;
}

export type SahteOgrenci = { id: string; ad: string; soyad: string; telefon: string; tc: string };

/** API ile hızlıca öğrenci oluşturur (benzersiz ad, TC ve telefon). */
export async function ogrenciOlusturAPI(page: Page, token: string, onek = "Api"): Promise<SahteOgrenci> {
  const k = benzersiz();
  const ad = `${onek}${k}`;
  const soyad = `Ogrenci${k}`;
  const telefon = "+90" + telefonUret10(); // kanonik API biçimi
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

export type YoklamaOrtami = {
  antrenor: { giris: string; sifre: string; adSoyad: string };
  grupAdi: string;
  geldi: SahteOgrenci;
  gelmedi: SahteOgrenci;
};

/**
 * Yönetici API'siyle yoklama senaryosunu kurar: antrenör, bugünün haftanın gününde programı olan
 * grup, iki öğrenci ve bugüne ait oturum. Sonunda çerezleri temizler (antrenör temiz girer).
 */
export async function yoklamaOrtamiKur(page: Page): Promise<YoklamaOrtami> {
  const token = await yoneticiApiGirisi(page);
  const yetki = { Authorization: `Bearer ${token}` };
  const k = benzersiz();
  const adSoyad = `Antrenor ${k}`;
  const giris = `antrenor.${k}@example.com`;

  const a = await page.request.post("/api/antrenorler", { headers: yetki, data: { ad_soyad: adSoyad, giris } });
  expect(a.status(), await a.text()).toBe(201);
  const antrenor = (await a.json()) as { antrenor: { id: string }; gecici_sifre: string };

  const bugun = new Date();
  const gun = ((bugun.getDay() + 6) % 7) + 1; // isoweekday: Pazartesi=1 ... Pazar=7
  const grupAdi = `Yoklama ${k}`;
  const g = await page.request.post("/api/gruplar", {
    headers: yetki,
    data: {
      ad: grupAdi,
      antrenor_id: antrenor.antrenor.id,
      kontenjan: 10,
      // 00:00–23:59: antrenörün yoklaması (15 dk kuralı) günün her saatinde açık olsun.
      program: [{ gun, baslangic: "00:00", bitis: "23:59" }],
    },
  });
  expect(g.status(), await g.text()).toBe(201);
  const grup = (await g.json()) as { id: string };

  const geldi = await ogrenciOlusturAPI(page, token, "Geldi");
  const gelmedi = await ogrenciOlusturAPI(page, token, "Gelmedi");
  for (const o of [geldi, gelmedi]) {
    const e = await page.request.post(`/api/gruplar/${grup.id}/ogrenciler`, { headers: yetki, data: { ogrenci_id: o.id } });
    expect(e.ok(), await e.text()).toBeTruthy();
  }

  const t = `${bugun.getFullYear()}-${String(bugun.getMonth() + 1).padStart(2, "0")}-${String(bugun.getDate()).padStart(2, "0")}`;
  const u = await page.request.post("/api/oturumlar/uret", { headers: yetki, data: { baslangic: t, bitis: t } });
  expect(u.ok(), await u.text()).toBeTruthy();
  expect(((await u.json()) as { olusturulan: number }).olusturulan).toBeGreaterThanOrEqual(1);

  // Geçici şifre zorunlu değişim bayrağıyla gelir; antrenör doğrudan takvime girebilsin diye şifreyi API ile belirler.
  await page.context().clearCookies();
  const l = await page.request.post("/api/auth/login", { data: { giris, sifre: antrenor.gecici_sifre } });
  expect(l.ok(), await l.text()).toBeTruthy();
  const at = ((await l.json()) as { access_token: string }).access_token;
  const d = await page.request.post("/api/auth/sifre-degistir", {
    headers: { Authorization: `Bearer ${at}` },
    data: { mevcut_sifre: antrenor.gecici_sifre, yeni_sifre: YENI_SIFRE },
  });
  expect(d.status(), await d.text()).toBe(204);

  await page.context().clearCookies();
  return { antrenor: { giris, sifre: YENI_SIFRE, adSoyad }, grupAdi, geldi, gelmedi };
}

/** API ile paket tanımı oluşturur. */
export async function paketOlusturAPI(
  page: Page,
  token: string,
  o: { ad?: string; ders_sayisi?: number; fiyat?: string; tur?: string; sure_ay?: number } = {},
): Promise<{ id: string; ad: string }> {
  const ad = o.ad ?? `E2E Paket ${benzersiz()}`;
  const yanit = await page.request.post("/api/paketler", {
    headers: { Authorization: `Bearer ${token}` },
    data: { ad, tur: o.tur ?? "aylik", ders_sayisi: o.ders_sayisi ?? 8, sure_ay: o.sure_ay ?? 1, varsayilan_fiyat: o.fiyat ?? "3400" },
  });
  expect(yanit.status(), await yanit.text()).toBe(201);
  return { id: ((await yanit.json()) as { id: string }).id, ad };
}

/** API ile öğrenciye paket atar; öğrenci paketi kimliğini döner. */
export async function paketAtaAPI(page: Page, token: string, ogrenciId: string, paketId: string): Promise<string> {
  const yanit = await page.request.post(`/api/ogrenciler/${ogrenciId}/paketler`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { paket_id: paketId },
  });
  expect(yanit.status(), await yanit.text()).toBe(201);
  return ((await yanit.json()) as { id: string }).id;
}

/** API ile öğrenci paketi için ödeme alır (tarih verilmezse bugün). */
export async function odemeAlAPI(page: Page, token: string, ogrenciPaketiId: string, yontem: "nakit" | "havale_eft" | "diger" = "nakit"): Promise<void> {
  const yanit = await page.request.post(`/api/ogrenci-paketleri/${ogrenciPaketiId}/odeme`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { yontem },
  });
  expect(yanit.ok(), await yanit.text()).toBeTruthy();
}

/** Gelir raporu yanıtı (yalnız ihtiyaç duyulan alanlar). */
export async function gelirRaporuAPI(page: Page, token: string, yil: number, ay: number) {
  const yanit = await page.request.get(`/api/raporlar/gelir?yil=${yil}&ay=${ay}`, { headers: { Authorization: `Bearer ${token}` } });
  expect(yanit.status(), await yanit.text()).toBe(200);
  return (await yanit.json()) as { ozet: { toplam_tahsilat: string; odeme_adedi: number } };
}
