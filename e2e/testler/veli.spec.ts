import { arayuzdenGiris, expect, geciciSifreyleGiris, zorunluSifreyiBelirle, ogrenciOlusturAPI, telefonBosluklu, telefonGorunen, test, yoneticiApiGirisi } from "../yardimci";

test.describe("Veli hesabı", () => {
  test("öğrenci detayından hesap açılır, veli boşluklu telefonla girip paneli görür", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const ogrenci = await ogrenciOlusturAPI(page, token, "Veli");

    await page.goto(`/ogrenciler/${ogrenci.id}`);
    await expect(page.getByRole("heading", { name: `${ogrenci.ad} ${ogrenci.soyad}` })).toBeVisible();
    await page.getByRole("button", { name: "Hesap aç" }).click();

    const sifreKutusu = page.getByRole("dialog", { name: /için geçici şifre/ });
    await expect(sifreKutusu).toBeVisible();
    const sifre = (await sifreKutusu.locator("code").innerText()).trim();
    await sifreKutusu.getByRole("button", { name: "Kapat" }).click();
    await expect(page.getByText(telefonGorunen(ogrenci.telefon)).first()).toBeVisible();

    await page.getByRole("button", { name: "Çıkış" }).click();
    await expect(page).toHaveURL(/\/yonetici-giris$/);

    await geciciSifreyleGiris(page, telefonBosluklu(ogrenci.telefon), sifre);
    await expect(page).toHaveURL(/\/panel\/cocuk\//);
    await expect(page.getByRole("heading", { name: `${ogrenci.ad} ${ogrenci.soyad}` })).toBeVisible();
    await expect(page.getByRole("link", { name: "Öğrenciler" })).toHaveCount(0);
  });

  test("veli geçici şifreyle girer, zorunlu ekranda zayıf şifre reddedilir, sonra yeni şifreyle girer", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const ogrenci = await ogrenciOlusturAPI(page, token, "Sifre");
    await page.goto(`/ogrenciler/${ogrenci.id}`);
    await page.getByRole("button", { name: "Hesap aç" }).click();
    const sifreKutusu = page.getByRole("dialog", { name: /için geçici şifre/ });
    const gecici = (await sifreKutusu.locator("code").innerText()).trim();
    await sifreKutusu.getByRole("button", { name: "Kapat" }).click();
    await page.getByRole("button", { name: "Çıkış" }).click();
    await expect(page).toHaveURL(/\/yonetici-giris$/);

    const giris = telefonBosluklu(ogrenci.telefon);
    await arayuzdenGiris(page, giris, gecici);
    await expect(page).toHaveURL(/\/sifre-degistir$/);
    await expect(page.getByRole("heading", { name: "Şifrenizi belirleyin" })).toBeVisible();

    // Korumalı rotalar zorunlu ekrana döner.
    await page.goto("/");
    await expect(page).toHaveURL(/\/sifre-degistir$/);

    // Zayıf şifreler istemcide reddedilir.
    await page.getByLabel("Mevcut (geçici) şifre").fill(gecici);
    await page.getByLabel("Yeni şifre", { exact: true }).fill("kisa1");
    await page.getByLabel("Yeni şifre (tekrar)").fill("kisa1");
    await page.getByRole("button", { name: "Şifreyi kaydet" }).click();
    await expect(page.getByText("en az 10 karakter")).toBeVisible();
    await page.getByLabel("Yeni şifre", { exact: true }).fill("sadeceharflerburada");
    await page.getByLabel("Yeni şifre (tekrar)").fill("sadeceharflerburada");
    await page.getByRole("button", { name: "Şifreyi kaydet" }).click();
    await expect(page.getByText("en az bir harf ve bir rakam")).toBeVisible();
    await expect(page).toHaveURL(/\/sifre-degistir$/);

    const yeni = "gucluyeni-sifre-2025";
    await zorunluSifreyiBelirle(page, gecici, yeni);
    await expect(page.getByRole("heading", { name: `${ogrenci.ad} ${ogrenci.soyad}` })).toBeVisible();
    await expect(page).toHaveURL(/\/panel\/cocuk\//);

    await page.getByRole("button", { name: "Çıkış" }).click();
    await expect(page).toHaveURL(/\/giris$/);
    await arayuzdenGiris(page, giris, yeni);
    await expect(page.getByRole("heading", { name: `${ogrenci.ad} ${ogrenci.soyad}` })).toBeVisible();
  });
});
