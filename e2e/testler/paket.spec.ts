import { arayuzdenGiris, benzersiz, expect, ogrenciOlusturAPI, test, yoneticiApiGirisi, YONETICI_GIRIS, YONETICI_SIFRE } from "../yardimci";

test.describe("Paketler", () => {
  test("yönetici paket tanımlar, öğrenciye atar (özel fiyatlı dahil) ve iptal eder", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const ogr = await ogrenciOlusturAPI(page, token, "Paket");
    const paketAdi = `E2E Aylık ${benzersiz()}`;

    await page.context().clearCookies();
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await expect(page).toHaveURL(/\/genel-bakis$/);

    // Paket tanımı
    await page.goto("/paketler");
    await page.getByRole("button", { name: "Yeni paket" }).click();
    const yeni = page.getByRole("dialog", { name: "Yeni paket" });
    await yeni.getByLabel("Paket adı").fill(paketAdi);
    await yeni.getByLabel("Tür").selectOption("aylik");
    await yeni.getByLabel("Ders sayısı").fill("8");
    await yeni.getByLabel("Varsayılan fiyat (₺)").fill("3400");
    await yeni.getByRole("button", { name: "Paketi oluştur" }).click();
    await expect(yeni).toHaveCount(0);
    const paketSatiri = page.getByRole("row").filter({ hasText: paketAdi });
    await expect(paketSatiri).toContainText("Aylık");
    await expect(paketSatiri).toContainText("3.400 ₺");
    await expect(paketSatiri).toContainText("Aktif");

    // Atama
    await page.goto(`/ogrenciler/${ogr.id}`);
    await expect(page.getByText("Öğrenciye henüz paket atanmamış.")).toBeVisible();

    const ata = async () => {
      await page.getByRole("button", { name: "Paket ata" }).click();
      const pencere = page.getByRole("dialog", { name: "Paket ata" });
      await pencere.getByRole("combobox", { name: "Paket", exact: true }).selectOption({ label: paketAdi });
      return pencere;
    };

    // Liste fiyatıyla
    let pencere = await ata();
    await expect(pencere).toContainText("3.400 ₺");
    await pencere.getByRole("button", { name: "Paketi ata" }).click();
    await expect(pencere).toHaveCount(0);
    await expect(page.getByRole("listitem").filter({ hasText: paketAdi })).toHaveCount(1);

    // Ödeme bekleyen paket varken ikinci atama reddedilir
    pencere = await ata();
    await pencere.getByRole("button", { name: "Paketi ata" }).click();
    await expect(pencere.getByRole("alert")).toContainText("ödeme bekleyen bir paketi var");
    await pencere.getByRole("button", { name: "Kapat" }).click();

    // İptal (window.confirm testte otomatik kabul edilir)
    const ilk = page.getByRole("listitem").filter({ hasText: paketAdi }).first();
    await ilk.getByRole("button", { name: /iptal et/i }).click();
    await expect(page.getByRole("listitem").filter({ hasText: paketAdi }).filter({ hasText: "İptal" })).toHaveCount(1);

    // Özel fiyat: nedensiz reddedilir
    pencere = await ata();
    await pencere.getByLabel("Özel fiyat uygula").check();
    await pencere.getByLabel("Özel fiyat (₺)").fill("3000");
    await pencere.getByRole("button", { name: "Paketi ata" }).click();
    await expect(pencere.getByRole("alert")).toContainText("neden");
    await expect(pencere).toBeVisible();

    // Nedenle kabul
    await pencere.getByLabel("Özel fiyat nedeni").fill("Kardeş indirimi");
    await pencere.getByRole("button", { name: "Paketi ata" }).click();
    await expect(pencere).toHaveCount(0);
    const ozel = page.getByRole("listitem").filter({ hasText: "Özel fiyat" });
    await expect(ozel).toContainText("3.000 ₺");
    await expect(ozel).toContainText("Ödeme bekliyor");
  });
});
