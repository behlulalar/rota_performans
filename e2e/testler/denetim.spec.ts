import { arayuzdenGiris, expect, ogrenciOlusturAPI, test, YONETICI_GIRIS, YONETICI_SIFRE, yoneticiApiGirisi } from "../yardimci";

test.describe("Denetim kaydı", () => {
  test("yönetici kayıtları görür ve işleme göre süzer", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    await ogrenciOlusturAPI(page, token, "Denetim");

    await page.context().clearCookies();
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await expect(page).toHaveURL(/\/genel-bakis$/);
    await page.goto("/denetim-kaydi");
    await expect(page.getByRole("heading", { name: "Denetim kaydı" })).toBeVisible();

    const satirlar = page.getByTestId("denetim-satiri");
    await expect(satirlar.first()).toBeVisible();
    await expect(page.getByText(/\d+–\d+ \/ \d+/)).toBeVisible();

    await page.getByRole("combobox", { name: "İşlem filtresi" }).selectOption("giris_basarili");
    // Süzgeç uygulanınca "Ödeme/Öğrenci" gibi başka işlemler kalmaz.
    await expect(satirlar.filter({ hasNotText: /giriş/i })).toHaveCount(0);
    await expect(satirlar.first()).toBeVisible();

    // Ayrıntı açılır.
    await satirlar.first().getByRole("button", { name: "Ayrıntı" }).click();
    await expect(satirlar.first().getByRole("button", { name: "Gizle" })).toBeVisible();

    // Eşleşmeyen arama boş durumu gösterir.
    await page.getByRole("searchbox", { name: "Ara" }).fill("kesinlikle-yok-zzz");
    await expect(page.getByText("Bu filtreyle denetim kaydı yok.")).toBeVisible();
  });
});
