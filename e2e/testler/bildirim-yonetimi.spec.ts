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
    await expect(page.getByRole("tab", { name: "Uygulama bildirimleri" })).toHaveAttribute("aria-selected", "true");

    // Liste ya boş mesajı ya da tablo/kart sayfalaması gösterir.
    await expect(page.getByText(/Bu filtrede bildirim yok\.|\d+ kayıt · Sayfa/)).toBeVisible();
    // WhatsApp sekmesi: kanal bazlı özet ve açıklama.
    await page.getByRole("tab", { name: "WhatsApp" }).click();
    // Numara bağlı değil: ortama göre "kurulmadı" (CI) ya da "bağlı değil" (Evolution tanımlı yerel ortam).
    await expect(page.getByTestId("wa-kurulmadi").or(page.getByTestId("wa-durumu"))).toContainText(/WhatsApp henüz kurulmadı|bağlı değil/);
    await expect(page.getByTestId("push-durumu")).toHaveCount(0);
    await page.getByRole("tab", { name: "Uygulama bildirimleri" }).click();
    await expect(page.getByTestId("push-durumu")).toBeVisible();

    await page.getByLabel("Durum filtresi").selectOption("hata");
    await page.getByLabel("Öğrenci ara").fill("yokboyleisim");
    await expect(page.getByText("Bu filtrede bildirim yok.")).toBeVisible();
  });
});
