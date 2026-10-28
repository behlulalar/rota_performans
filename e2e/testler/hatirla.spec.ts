import { arayuzdenGiris, expect, test, YONETICI_GIRIS, YONETICI_SIFRE } from "../yardimci";
import type { Page } from "@playwright/test";

const GUN_MS = 86_400_000;

async function hatirlaIsaretliGiris(page: Page): Promise<void> {
  await page.goto("/yonetici-giris");
  await page.getByLabel("Telefon veya e-posta").fill(YONETICI_GIRIS);
  await page.getByLabel("Şifre", { exact: true }).fill(YONETICI_SIFRE);
  await page.getByLabel("Beni hatırla").check();
  await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
  // Giriş hız sınırına takılırsa pencere dolunca yeniden dener.
  const sinir = page.getByRole("alert").filter({ hasText: "Çok fazla deneme" });
  for (let i = 0; i < 3; i++) {
    if (!(await sinir.waitFor({ state: "visible", timeout: 2000 }).then(() => true, () => false))) break;
    await page.waitForTimeout(20_000);
    await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
  }
}

async function yenilemeCerezi(page: Page) {
  return (await page.context().cookies()).find((c) => c.name === "rota_yenileme");
}

test.describe("Beni hatırla", () => {
  test("hatırla işaretli giriş; çıkıştan sonra 'Tekrar hoş geldiniz' kartı ve yalnız şifreyle giriş", async ({ page }) => {
    await hatirlaIsaretliGiris(page);
    await expect(page).toHaveURL(/\/genel-bakis$/);

    await page.getByRole("button", { name: "Çıkış" }).click();
    await expect(page).toHaveURL(/\/yonetici-giris$/);
    await expect(page.getByText("Tekrar hoş geldiniz")).toBeVisible();
    // Kendi çıkışında "oturum süreniz doldu" uyarısı çıkmamalı (yalnız gerçek süre dolumunda).
    await expect(page.getByText("Oturum süreniz doldu")).toHaveCount(0);
    await expect(page.getByLabel("Telefon veya e-posta")).toHaveCount(0);
    await expect(page.getByText(YONETICI_GIRIS, { exact: true })).toBeVisible();
    await expect(page.getByLabel("Beni hatırla")).toBeChecked();

    await page.getByLabel("Şifre", { exact: true }).fill(YONETICI_SIFRE);
    await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
    await expect(page).toHaveURL(/\/genel-bakis$/);
  });

  test("'Başka hesapla giriş yap' normal formu açar, kutu işaretsiz ve kayıt temiz", async ({ page }) => {
    await hatirlaIsaretliGiris(page);
    await expect(page).toHaveURL(/\/genel-bakis$/);
    await page.getByRole("button", { name: "Çıkış" }).click();
    await expect(page.getByText("Tekrar hoş geldiniz")).toBeVisible();

    await page.getByRole("button", { name: "Başka hesapla giriş yap" }).click();
    await expect(page.getByLabel("Telefon veya e-posta")).toBeVisible();
    await expect(page.getByText("Tekrar hoş geldiniz")).toHaveCount(0);
    await expect(page.getByLabel("Beni hatırla")).not.toBeChecked();
    expect(await page.evaluate(() => localStorage.getItem("rota-hatirla"))).toBeNull();
    expect(await page.evaluate(() => localStorage.getItem("rota-hatirla-tercih"))).toBeNull();
  });

  test("hatırlamasız giriş oturum çerezi bırakır; çıkıştan sonra kart yok, normal form", async ({ page }) => {
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await expect(page).toHaveURL(/\/genel-bakis$/);
    const cerez = await yenilemeCerezi(page);
    expect(cerez).toBeTruthy();
    expect(cerez!.expires).toBe(-1);

    await page.getByRole("button", { name: "Çıkış" }).click();
    await expect(page).toHaveURL(/\/yonetici-giris$/);
    await expect(page.getByLabel("Telefon veya e-posta")).toBeVisible();
    await expect(page.getByText("Tekrar hoş geldiniz")).toHaveCount(0);
  });

  test("hatırlamalı girişte yenileme çerezi yaklaşık 30 gün sonra sona erer", async ({ page }) => {
    await hatirlaIsaretliGiris(page);
    await expect(page).toHaveURL(/\/genel-bakis$/);
    const cerez = await yenilemeCerezi(page);
    expect(cerez).toBeTruthy();
    const kalanGun = (cerez!.expires * 1000 - Date.now()) / GUN_MS;
    expect(kalanGun).toBeGreaterThan(29);
    expect(kalanGun).toBeLessThanOrEqual(30.01);
  });
});
