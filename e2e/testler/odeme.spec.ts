import { arayuzdenGiris, expect, ogrenciOlusturAPI, paketAtaAPI, paketOlusturAPI, test, yoneticiApiGirisi, YONETICI_GIRIS, YONETICI_SIFRE } from "../yardimci";

test.describe("Ödemeler", () => {
  test("ödeme al, ders hakkı yüklensin, Ödemeler sayfasında görünsün, nedenle geri al", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const ogr = await ogrenciOlusturAPI(page, token, "Odeme");
    const paket = await paketOlusturAPI(page, token, { ders_sayisi: 8, fiyat: "3400" });
    await paketAtaAPI(page, token, ogr.id, paket.id);
    const tamAd = `${ogr.ad} ${ogr.soyad}`;

    await page.context().clearCookies();
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await expect(page).toHaveURL(/\/genel-bakis$/);

    const kalan = page.getByText("Kalan ders", { exact: true }).locator("..");

    // Ödeme bekleyenler listesinde görünür
    await page.goto("/odemeler");
    const bekleyen = page.getByTestId("bekleyenler");
    await expect(bekleyen).toContainText(tamAd);
    await expect(bekleyen).toContainText(paket.ad);

    // Öğrenci kartında ödeme al
    await page.goto(`/ogrenciler/${ogr.id}`);
    await expect(kalan).toContainText("0");
    const satirPaket = page.getByRole("listitem").filter({ hasText: paket.ad }).first();
    await expect(satirPaket).toContainText("Ödeme bekliyor");
    await page.getByRole("button", { name: `${paket.ad} için ödeme al` }).click();
    const pencere = page.getByRole("dialog", { name: "Ödeme al" });
    await expect(pencere).toContainText("3.400 ₺");
    await pencere.getByLabel("Ödeme yöntemi").selectOption("nakit");
    await pencere.getByRole("button", { name: "Ödemeyi onayla" }).click();
    await expect(pencere).toContainText("8 ders hakkı yüklendi");
    await pencere.getByRole("button", { name: "Tamam" }).click();
    await expect(pencere).toHaveCount(0);

    await expect(satirPaket).toContainText("Ödendi");
    await expect(satirPaket).toContainText("3.400 ₺");
    await expect(kalan).toContainText("8");
    // Ödeme ayrıntıları "Detay" penceresinde liste olarak görünür.
    await satirPaket.getByRole("button", { name: `${paket.ad} detayı` }).click();
    const detay = page.getByRole("dialog", { name: "Paket detayı" });
    await expect(detay).toContainText("Nakit");
    await expect(detay).toContainText("3.400 ₺");
    await expect(detay).toContainText("Ödenen");
    await detay.getByRole("button", { name: "Kapat", exact: true }).last().click();
    await expect(detay).toHaveCount(0);

    // Ödemeler sayfası
    await page.goto("/odemeler");
    await page.getByLabel("Öğrenci ara").fill(ogr.ad);
    const tablo = page.getByRole("table", { name: "Ödemeler" });
    const odemeSatiri = tablo.getByRole("row").filter({ hasText: tamAd });
    await expect(odemeSatiri).toHaveCount(1);
    await expect(odemeSatiri).toContainText("3.400 ₺");
    await expect(odemeSatiri).toContainText("Nakit");
    await expect(odemeSatiri).toContainText("Alındı");
    // Arama bu öğrenciye daraltıldı: toplam yalnız bu ödeme
    await expect(page.getByText("Toplam tahsilat").locator("..")).toContainText("3.400 ₺");
    await expect(page.getByTestId("bekleyenler")).not.toContainText(tamAd);

    // Geri al: neden zorunlu
    await page.goto(`/ogrenciler/${ogr.id}`);
    await page.getByRole("button", { name: `${paket.ad} detayı` }).click();
    await page.getByRole("dialog", { name: "Paket detayı" }).getByRole("button", { name: /ödemeyi geri al/i }).click();
    const geriAl = page.getByRole("dialog", { name: "Ödemeyi geri al" });
    await expect(geriAl).toContainText("ders hakkı da geri alınır");
    await geriAl.getByRole("button", { name: "Ödemeyi geri al" }).click();
    await expect(geriAl.getByRole("alert")).toContainText("3 ile 200");
    await geriAl.getByLabel("Geri alma nedeni").fill("Yanlış tutar girildi");
    await geriAl.getByRole("button", { name: "Ödemeyi geri al" }).click();
    await expect(geriAl).toHaveCount(0);

    await expect(satirPaket).toContainText("Ödeme bekliyor");
    await expect(kalan).toContainText("0");
    await satirPaket.getByRole("button", { name: `${paket.ad} detayı` }).click();
    const gecmis = page.getByRole("dialog", { name: "Paket detayı" });
    await expect(gecmis).toContainText("Geri alındı");
    await expect(gecmis).toContainText("Yanlış tutar girildi");
    await gecmis.getByRole("button", { name: "Kapat", exact: true }).last().click();

    // Yeniden ödeme bekleyenlerde
    await page.goto("/odemeler");
    await expect(page.getByTestId("bekleyenler")).toContainText(tamAd);
  });
});
