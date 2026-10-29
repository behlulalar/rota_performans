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

  test("kayıtlı tercih yoksa yönetici sayfaları sistem renk şemasını izler", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/yonetici-giris");
    expect(await tema(page)).toBe("light");
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/antrenor-giris");
    expect(await tema(page)).toBe("dark");
  });

  test("veli sayfaları cihaz koyu olsa bile açık temayla başlar; seçilen tema hatırlanır", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/giris");
    expect(await tema(page)).toBe("light");
    await page.getByRole("button", { name: "Koyu temaya geç" }).click();
    await page.reload();
    expect(await tema(page)).toBe("dark");
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

  test("Sistem öğeleri 'Yakında' etiketli ve tıklanamaz; gerçek bağlantılar çalışır", async ({ page }) => {
    await yoneticiApiGirisi(page);
    await page.goto("/gruplar");
    await expect(page.getByRole("heading", { name: "Gruplar" })).toBeVisible();
    const url = page.url();
    const menu = page.getByRole("complementary", { name: "Menü" });

    for (const ad of ["Bildirimler", "Denetim kaydı", "Ayarlar"]) {
      const oge = menu.locator('[aria-disabled="true"]', { hasText: ad });
      await expect(oge).toBeVisible();
      await expect(oge).toContainText("Yakında");
      await oge.click({ force: true });
      await expect(page).toHaveURL(url);
      await expect(menu.getByRole("link", { name: ad })).toHaveCount(0);
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
