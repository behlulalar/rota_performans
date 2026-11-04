import { benzersiz, expect, geciciSifreyleGiris, test, yoneticiApiGirisi } from "../yardimci";

test.describe("Antrenör", () => {
  test("oluşturulur, geçici şifreyle girer ve yönetici menüsünü görmez", async ({ page }) => {
    await yoneticiApiGirisi(page);
    const k = benzersiz();
    const adSoyad = `Antrenor ${k}`;
    const giris = `antrenor.${k}@example.com`;

    await page.goto("/antrenorler");
    await page.getByRole("button", { name: "Yeni antrenör" }).click();
    const form = page.getByRole("dialog", { name: "Yeni antrenör" });
    await form.getByLabel("Ad soyad").fill(adSoyad);
    await form.getByLabel(/Giriş \(e-posta/).fill(giris);
    await form.getByRole("button", { name: "Oluştur" }).click();

    const sifreKutusu = page.getByRole("dialog", { name: `${adSoyad} için geçici şifre` });
    await expect(sifreKutusu).toBeVisible();
    const sifre = (await sifreKutusu.locator("code").innerText()).trim();
    expect(sifre.length).toBeGreaterThanOrEqual(8);
    await sifreKutusu.getByRole("button", { name: "Kapat" }).click();
    await expect(page.getByRole("row", { name: new RegExp(adSoyad) })).toBeVisible();

    await page.getByRole("button", { name: "Çıkış" }).click();
    await expect(page).toHaveURL(/\/yonetici-giris$/);

    await geciciSifreyleGiris(page, giris, sifre);
    await expect(page).toHaveURL(/\/bugun$/);
    await expect(page.getByRole("heading", { name: "Bugün", exact: true, level: 1 })).toBeVisible();
    for (const menu of ["Öğrenciler", "Antrenörler", "Gruplar", "Genel bakış"]) {
      await expect(page.getByRole("link", { name: menu, exact: true })).toHaveCount(0);
    }

    // Yönetici sayfasına doğrudan gitse bile Bugün sayfasına döner.
    await page.goto("/antrenorler");
    await expect(page).toHaveURL(/\/bugun$/);
  });
});
