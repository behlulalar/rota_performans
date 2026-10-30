import { destekApiGirisi, expect, ogrenciOlusturAPI, test, yoneticiApiGirisi } from "../yardimci";

test.describe("Denetim kaydı", () => {
  test("teknik destek kayıtları görür ve işleme göre süzer", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    await ogrenciOlusturAPI(page, token, "Denetim");

    await page.context().clearCookies();
    await destekApiGirisi(page);
    await page.goto("/destek/denetim-kaydi");
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

  test("yönetici denetim kaydına erişemez", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const yanit = await page.request.get("/api/denetim", { headers: { Authorization: `Bearer ${token}` } });
    expect(yanit.status()).toBe(403);
    await page.goto("/destek/denetim-kaydi");
    await expect(page).toHaveURL(/\/genel-bakis$/);
  });
});
