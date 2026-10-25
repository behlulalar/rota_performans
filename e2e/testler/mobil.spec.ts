import { arayuzdenGiris, expect, ogrenciOlusturAPI, test, YONETICI_GIRIS, YONETICI_SIFRE, yoklamaOrtamiKur, yoneticiApiGirisi } from "../yardimci";

// Bu dosya yalnızca "mobil" (Pixel 7) projesinde çalışır.
test("mobilde giriş yapılır, öğrenci listesi kart görünümünde açılır ve menü çekmecesi çalışır", async ({ page }) => {
  const token = await yoneticiApiGirisi(page);
  const ogrenci = await ogrenciOlusturAPI(page, token, "Mobil");
  await page.context().clearCookies();

  await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
  await expect(page).toHaveURL(/\/genel-bakis$/);
  await page.goto("/ogrenciler");
  await page.getByPlaceholder("Ad veya soyad ara…").fill(ogrenci.soyad);

  // Kart görünümü: tablo gizli, öğrenci kartı bağlantı olarak görünür.
  await expect(page.getByRole("link", { name: new RegExp(`${ogrenci.ad} ${ogrenci.soyad}`) })).toBeVisible();
  await expect(page.getByRole("table")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Menüyü aç/kapat" })).toBeVisible();

  // Menü çekmecesi: masaüstü şeridi ve alt menüsü mobilde görünmez.
  await expect(page.getByRole("complementary")).toHaveCount(0);

  const dugme = page.getByRole("button", { name: "Menüyü aç/kapat" });
  await dugme.click();
  const cekmece = page.getByRole("dialog", { name: "Menü" });
  await expect(cekmece).toBeVisible();
  await expect(cekmece.getByRole("link", { name: "Genel bakış" })).toBeVisible();
  await expect(cekmece.getByRole("link", { name: "Takvim" })).toBeVisible();
  await expect(cekmece.getByRole("link", { name: "Antrenörler" })).toBeVisible();
  await expect(cekmece.getByRole("link", { name: "Gelir raporu" })).toBeVisible();
  await expect(cekmece.locator('[aria-disabled="true"]', { hasText: "Bildirimler" })).toContainText("Yakında");
  await expect(cekmece.getByRole("button", { name: /temaya geç/ })).toBeVisible();
  await expect(cekmece.getByRole("button", { name: "Çıkış" })).toBeVisible();

  await cekmece.getByRole("link", { name: "Gruplar" }).click();
  await expect(page).toHaveURL(/\/gruplar$/);
  await expect(page.getByRole("heading", { name: "Gruplar" })).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Menü" })).toHaveCount(0);
});

test("mobilde alt sekme çubuğu: seçili sekme vurgulanır, Takvim sekmesi /takvim'e gider, Menü çekmeceyi açar", async ({ page }) => {
  await yoneticiApiGirisi(page);
  await page.goto("/ogrenciler");
  await expect(page.getByRole("heading", { name: "Öğrenciler" })).toBeVisible();

  const sekmeler = page.getByRole("navigation", { name: "Hızlı sekmeler" });
  await expect(sekmeler).toBeVisible();
  for (const ad of ["Genel bakış", "Takvim", "Öğrenciler", "Gruplar"]) {
    await expect(sekmeler.getByRole("link", { name: ad })).toBeVisible();
  }
  await expect(sekmeler.getByRole("button", { name: "Menü" })).toBeVisible();
  await expect(sekmeler.getByRole("link", { name: "Öğrenciler" })).toHaveAttribute("aria-current", "page");
  await expect(sekmeler.getByRole("link", { name: "Takvim" })).not.toHaveAttribute("aria-current", "page");

  // Çubuk en az 56px yüksekliktedir ve ekranın altına yapışıktır.
  const kutu = await sekmeler.boundingBox();
  const gorunum = page.viewportSize()!;
  expect(kutu!.height).toBeGreaterThanOrEqual(56);
  expect(Math.round(kutu!.y + kutu!.height)).toBe(gorunum.height);

  // Sayfa sonuna inildiğinde içerik çubuğun altında kalmaz.
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  const sonOge = await page.locator("main > *").last().evaluate((m) => m.getBoundingClientRect().bottom);
  expect(sonOge).toBeLessThanOrEqual(kutu!.y + 1);

  await sekmeler.getByRole("link", { name: "Takvim" }).click();
  await expect(page).toHaveURL(/\/takvim$/);
  await expect(page.getByRole("heading", { name: "Takvim" })).toBeVisible();
  await expect(sekmeler.getByRole("link", { name: "Takvim" })).toHaveAttribute("aria-current", "page");

  await sekmeler.getByRole("button", { name: "Menü" }).click();
  await expect(page.getByRole("dialog", { name: "Menü" })).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Menü" }).getByRole("button", { name: "Çıkış" })).toBeVisible();
});

test("mobilde antrenörde alt sekme çubuğu yoktur", async ({ page }) => {
  const o = await yoklamaOrtamiKur(page);
  await arayuzdenGiris(page, o.antrenor.giris, o.antrenor.sifre);
  await expect(page).toHaveURL(/\/takvim$/);
  await expect(page.getByRole("navigation", { name: "Hızlı sekmeler" })).toHaveCount(0);
});

test("mobilde antrenör takvimi ve yoklama ekranı açılır", async ({ page }) => {
  const o = await yoklamaOrtamiKur(page);

  await arayuzdenGiris(page, o.antrenor.giris, o.antrenor.sifre);
  await expect(page).toHaveURL(/\/takvim$/);
  // Bugün açık gelir: oturum kartı görünür.
  const kart = page.getByRole("link", { name: new RegExp(o.grupAdi) });
  await expect(kart).toBeVisible();
  await kart.click();

  await expect(page.getByRole("heading", { name: o.grupAdi })).toBeVisible();
  await expect(page.getByRole("button", { name: "Tümü geldi" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Geldi", exact: true })).toHaveCount(2);
  await page.getByRole("button", { name: "Tümü geldi" }).click();
  await expect(page.getByRole("button", { name: "Yoklamayı kaydet (2/2 işaretli)" })).toBeVisible();
});
