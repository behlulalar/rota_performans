import { expect, test, yoneticiApiGirisi } from "../yardimci";

const tema = (page: import("@playwright/test").Page) =>
  page.evaluate(() => document.documentElement.dataset.theme);

test.describe("Tema", () => {
  test("yönetici giriş sayfasında tema düğmesi temayı değiştirir ve tercih yenilemede korunur", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/yonetici-giris");
    expect(await tema(page)).toBe("dark");
    const govdeKoyu = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);

    await page.getByRole("button", { name: "Açık temaya geç" }).click();
    expect(await tema(page)).toBe("light");
    expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).not.toBe(govdeKoyu);
    expect(await page.evaluate(() => localStorage.getItem("rota-tema-2"))).toBe("light");

    await page.reload();
    expect(await tema(page)).toBe("light");
    await expect(page.getByRole("button", { name: "Koyu temaya geç" })).toBeVisible();

    await page.getByRole("button", { name: "Koyu temaya geç" }).click();
    expect(await tema(page)).toBe("dark");
    await page.reload();
    expect(await tema(page)).toBe("dark");
  });

  test("kayıtlı tercih yoksa tüm girişler cihaz açık olsa bile koyu temayla başlar", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    for (const yol of ["/giris", "/yonetici-giris", "/antrenor-giris"]) {
      await page.goto(yol);
      expect(await tema(page), yol).toBe("dark");
    }
  });

  test("veli sayfalarında seçilen açık tema hatırlanır; koyuya dönünce o da hatırlanır", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/giris");
    expect(await tema(page)).toBe("dark");
    await page.getByRole("button", { name: "Açık temaya geç" }).click();
    await page.reload();
    expect(await tema(page)).toBe("light");
    await page.goto("/yonetici-giris");
    expect(await tema(page)).toBe("light");
  });
});

test.describe("Yönetici menüsü", () => {
  test("sol menü gruplu ve her zaman açık; aktif öğe işaretlenir; tema tercihi yenilemede korunur", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await yoneticiApiGirisi(page);
    await page.goto("/ogrenciler");
    await expect(page.getByRole("heading", { name: "Öğrenciler" })).toBeVisible();

    // Üstteki siyah çubukta tema düğmesi çalışır ve tercih korunur.
    expect(await tema(page)).toBe("dark");
    await page.getByRole("button", { name: "Açık temaya geç" }).click();
    expect(await tema(page)).toBe("light");
    await page.reload();
    await expect(page.getByRole("heading", { name: "Öğrenciler" })).toBeVisible();
    expect(await tema(page)).toBe("light");

    const menu = page.getByRole("complementary", { name: "Menü" });
    await expect(menu).toBeVisible();
    await expect(menu.getByRole("link", { name: "Öğrenciler" })).toHaveAttribute("aria-current", "page");
    for (const ad of ["Genel bakış", "Takvim", "Antrenörler", "Gruplar", "Ödemeler", "Paketler", "Gelir raporu"]) {
      await expect(menu.getByRole("link", { name: ad })).toBeVisible();
    }
  });

  test("Sistem öğeleri (Bildirimler, Ayarlar) bağlantıdır ve sayfaları açar", async ({ page }) => {
    await yoneticiApiGirisi(page);
    await page.goto("/gruplar");
    await expect(page.getByRole("heading", { name: "Gruplar" })).toBeVisible();
    const menu = page.getByRole("complementary", { name: "Menü" });
    await expect(menu.locator('[aria-disabled="true"]')).toHaveCount(0);

    for (const [ad, yol] of [["Bildirimler", "/bildirimler"], ["Ayarlar", "/ayarlar"]]) {
      await menu.getByRole("link", { name: ad }).click();
      await expect(page).toHaveURL(new RegExp(`${yol}$`));
      await expect(page.getByRole("heading", { name: ad, level: 1 })).toBeVisible();
    }

    await menu.getByRole("link", { name: "Genel bakış" }).click();
    await expect(page).toHaveURL(/\/genel-bakis$/);
    await expect(page.getByRole("heading", { name: "Genel bakış" })).toBeVisible();
  });

  test("sol menü üstteki düğmeyle gizlenip açılır; tercih yenilemede korunur", async ({ page }) => {
    await yoneticiApiGirisi(page);
    await page.goto("/gruplar");
    const menu = page.getByRole("complementary", { name: "Menü" });
    await expect(menu).toBeVisible();

    await page.getByRole("button", { name: "Menüyü gizle" }).click();
    await expect(menu).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Gruplar" })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("heading", { name: "Gruplar" })).toBeVisible();
    await expect(menu).toHaveCount(0);

    await page.getByRole("button", { name: "Menüyü göster" }).click();
    await expect(menu).toBeVisible();
    await expect(menu.getByRole("link", { name: "Gruplar" })).toHaveAttribute("aria-current", "page");
  });
});
