import { arayuzdenGiris, expect, ogrenciOlusturAPI, telefonBosluklu, test, yoneticiApiGirisi } from "../yardimci";

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
    await expect(page.getByText(ogrenci.telefon).first()).toBeVisible();

    await page.getByRole("button", { name: "Çıkış" }).click();
    await expect(page).toHaveURL(/\/giris$/);

    await arayuzdenGiris(page, telefonBosluklu(ogrenci.telefon), sifre);
    await expect(page.getByRole("heading", { name: "Hoş geldiniz" })).toBeVisible();
    await expect(page.getByText("Veli paneli yakında burada olacak.")).toBeVisible();
    await expect(page.getByRole("link", { name: "Öğrenciler" })).toHaveCount(0);
  });
});
