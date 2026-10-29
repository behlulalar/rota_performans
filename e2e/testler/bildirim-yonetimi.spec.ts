import { arayuzdenGiris, expect, test, YONETICI_GIRIS, YONETICI_SIFRE } from "../yardimci";

test.describe("Bildirimler (yönetici)", () => {
  test("özet, push durumu ve liste görünür", async ({ page }) => {
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await page.getByRole("link", { name: "Bildirimler" }).first().click();
    await expect(page).toHaveURL(/\/bildirimler$/);
    await expect(page.getByRole("heading", { name: "Bildirimler" })).toBeVisible();

    const ozet = page.getByTestId("bildirim-ozet");
    for (const e of ["Bekliyor", "Gönderildi", "Hatalı", "İptal"]) await expect(ozet).toContainText(e);
    await expect(page.getByTestId("push-durumu")).toContainText("Uygulama bildirimleri:");
    await expect(page.getByTestId("push-durumu")).toContainText("cihaz kayıtlı");
    await expect(page.getByText("WhatsApp gönderimi Evolution API bağlandığında etkinleşecek.")).toBeVisible();

    // Liste ya boş mesajı ya da tablo/kart sayfalaması gösterir.
    await expect(page.getByText(/Bu filtrede bildirim yok\.|\d+ kayıt · Sayfa/)).toBeVisible();
    await page.getByLabel("Durum filtresi").selectOption("hata");
    await page.getByLabel("Öğrenci ara").fill("yokboyleisim");
    await expect(page.getByText("Bu filtrede bildirim yok.")).toBeVisible();
  });
});
