import { benzersiz, expect, ogrenciOlusturAPI, test, yoneticiApiGirisi } from "../yardimci";

test.describe("Grup", () => {
  test("kontenjanı 1 olan gruba ilk öğrenci eklenir, ikincisi kontenjan dolu uyarısı alır", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const birinci = await ogrenciOlusturAPI(page, token, "Birinci");
    const ikinci = await ogrenciOlusturAPI(page, token, "Ikinci");
    const grupAdi = `Grup ${benzersiz()}`;

    await page.goto("/gruplar/yeni");
    await page.getByLabel("Grup adı").fill(grupAdi);
    await page.getByLabel("Kontenjan").fill("1");
    await page.getByRole("button", { name: "Satır ekle" }).click();
    await page.getByLabel("Başlangıç").fill("18:00");
    await page.getByLabel("Bitiş").fill("19:30");
    await page.getByRole("button", { name: "Kaydet" }).click();

    await expect(page).toHaveURL(/\/gruplar\/[0-9a-f-]{36}$/);
    await expect(page.getByRole("heading", { name: grupAdi })).toBeVisible();
    await expect(page.getByText("Pazartesi 18:00–19:30")).toBeVisible();
    await expect(page.getByText("0 / 1")).toBeVisible();

    const ara = page.getByPlaceholder("Aktif öğrenci ara…");
    await ara.fill(birinci.soyad);
    await page.getByRole("listitem").filter({ hasText: birinci.ad }).getByRole("button", { name: "Ekle" }).click();
    await expect(page.getByText("1 / 1")).toBeVisible();
    await expect(page.getByRole("link", { name: `${birinci.ad} ${birinci.soyad}` })).toBeVisible();

    await ara.fill(ikinci.soyad);
    await page.getByRole("listitem").filter({ hasText: ikinci.ad }).getByRole("button", { name: "Ekle" }).click();
    await expect(page.getByRole("alert")).toContainText(/kontenjan.* dolu/i);
    await expect(page.getByText("1 / 1")).toBeVisible();
    await expect(page.getByRole("link", { name: `${ikinci.ad} ${ikinci.soyad}` })).toHaveCount(0);
  });
});
