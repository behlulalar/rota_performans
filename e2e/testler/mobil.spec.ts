import { arayuzdenGiris, expect, ogrenciOlusturAPI, test, YONETICI_GIRIS, YONETICI_SIFRE, yoklamaOrtamiKur, yoneticiApiGirisi } from "../yardimci";

// Bu dosya yalnızca "mobil" (Pixel 7) projesinde çalışır.
test("mobilde giriş yapılır ve öğrenci listesi kart görünümünde açılır", async ({ page }) => {
  const token = await yoneticiApiGirisi(page);
  const ogrenci = await ogrenciOlusturAPI(page, token, "Mobil");
  await page.context().clearCookies();

  await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
  await expect(page).toHaveURL(/\/ogrenciler$/);
  await page.getByPlaceholder("Ad veya soyad ara…").fill(ogrenci.soyad);

  // Kart görünümü: tablo gizli, öğrenci kartı bağlantı olarak görünür.
  await expect(page.getByRole("link", { name: new RegExp(`${ogrenci.ad} ${ogrenci.soyad}`) })).toBeVisible();
  await expect(page.getByRole("table")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Menüyü aç/kapat" })).toBeVisible();
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
