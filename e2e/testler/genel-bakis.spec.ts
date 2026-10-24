import { expect, test, yoneticiApiGirisi, yoklamaOrtamiKur } from "../yardimci";

test.describe("Genel bakış", () => {
  test("özet kartları, bugünün dersi ve yapılacaklar şeridi gerçek veriyle dolar", async ({ page }) => {
    const o = await yoklamaOrtamiKur(page);
    await yoneticiApiGirisi(page);
    await page.goto("/genel-bakis");

    await expect(page.getByRole("heading", { level: 1, name: "Genel Bakış" })).toBeVisible();
    await expect(page.getByText(/\d+ aktif öğrenci \(\d+ pasif\) · \d+ grup · bugün \d+ ders/)).toBeVisible();
    await expect(page.getByRole("link", { name: "Takvimi aç" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Yeni öğrenci" })).toBeVisible();

    for (const etiket of ["Aktif öğrenci", "Grup doluluğu", "Aktif antrenör", "Bekleyen ödeme", "Bugünkü ders"]) {
      await expect(page.getByText(etiket, { exact: true }).first()).toBeVisible();
    }

    // Başlangıcı 00:00 olan bugünkü ders: yoklaması bekliyor.
    const dersler = page.locator("section", { has: page.getByRole("heading", { name: "Bugünün dersleri" }) });
    const satir = dersler.getByRole("listitem").filter({ hasText: o.grupAdi });
    await expect(satir).toBeVisible();
    await expect(satir).toContainText("Bekliyor");
    await expect(satir).toContainText(o.antrenor.adSoyad);

    const serit = page.locator("section", { has: page.getByRole("heading", { name: "Bugün yapılacaklar" }) });
    await expect(serit.getByRole("link", { name: /Yoklaması bekleyen ders/ })).toBeVisible();

    await satir.getByRole("link", { name: o.grupAdi }).click();
    await expect(page).toHaveURL(/\/oturum\/[0-9a-f-]{36}$/);
  });
});
