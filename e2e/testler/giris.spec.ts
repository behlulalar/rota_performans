import { arayuzdenGiris, expect, test, YONETICI_GIRIS, YONETICI_SIFRE } from "../yardimci";

test.describe("Giriş", () => {
  test("yanlış şifre hata mesajı gösterir ve giriş yapılmaz", async ({ page }) => {
    await arayuzdenGiris(page, YONETICI_GIRIS, "tamamen-yanlis-sifre");
    await expect(page.getByRole("alert")).toContainText("Giriş bilgileri hatalı");
    await expect(page).toHaveURL(/\/giris$/);
  });

  test("doğru şifre yöneticiyi öğrenci listesine yönlendirir, çıkış giriş sayfasına döner", async ({ page }) => {
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await expect(page).toHaveURL(/\/ogrenciler$/);
    await expect(page.getByRole("heading", { name: "Öğrenciler" })).toBeVisible();

    await page.getByRole("button", { name: "Çıkış" }).click();
    await expect(page).toHaveURL(/\/giris$/);

    // Çıkıştan sonra korumalı sayfa tekrar girişe yönlendirir.
    await page.goto("/ogrenciler");
    await expect(page).toHaveURL(/\/giris$/);
  });
});
