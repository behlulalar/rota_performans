import { benzersiz, expect, geciciSifreyleGiris, test, yeniAntrenorGirisi, yoneticiApiGirisi } from "../yardimci";

test.describe("Antrenör", () => {
  test("oluşturulur, geçici şifreyle girer ve yönetici menüsünü görmez", async ({ page }) => {
    await yoneticiApiGirisi(page);
    const k = benzersiz();
    const adSoyad = `Antrenor ${k}`;
    const giris = yeniAntrenorGirisi();
    const grupAdi = `Grup ${k}`;
    const token = await yoneticiApiGirisi(page);
    const g = await page.request.post("/api/gruplar", {
      headers: { Authorization: `Bearer ${token}` },
      data: { ad: grupAdi, kontenjan: 10, program: [{ gun: 2, baslangic: "17:00", bitis: "18:00" }] },
    });
    expect(g.status(), await g.text()).toBe(201);

    await page.goto("/antrenorler");
    await page.getByRole("button", { name: "Yeni antrenör" }).click();
    const form = page.getByRole("dialog", { name: "Yeni antrenör" });
    await form.getByLabel("Ad soyad").fill(adSoyad);
    await form.getByLabel("Telefon").fill(giris);
    await expect(form.getByLabel(/Giriş \(e-posta/)).toHaveCount(0);
    await form.getByRole("checkbox", { name: new RegExp(grupAdi) }).check();
    await form.getByRole("button", { name: "Oluştur" }).click();

    const sifreKutusu = page.getByRole("dialog", { name: `${adSoyad} için geçici şifre` });
    await expect(sifreKutusu).toBeVisible();
    const sifre = (await sifreKutusu.locator("code").innerText()).trim();
    expect(sifre.length).toBeGreaterThanOrEqual(8);
    await sifreKutusu.getByRole("button", { name: "Kapat" }).click();
    const satir = page.getByRole("row", { name: new RegExp(adSoyad) });
    await expect(satir).toBeVisible();

    // Düzenleme penceresinde grup seçili gelir.
    await satir.getByRole("button", { name: "Düzenle" }).click();
    const duzen = page.getByRole("dialog", { name: "Antrenörü düzenle" });
    await expect(duzen.getByRole("checkbox", { name: new RegExp(grupAdi) })).toBeChecked();
    // Telefon değişmediyse giriş değişikliği uyarısı çıkmaz.
    await expect(duzen).not.toContainText("açık oturumları kapanır");
    await duzen.getByRole("button", { name: "Kapat" }).click();

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
