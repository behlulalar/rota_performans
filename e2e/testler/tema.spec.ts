import { expect, test, yoneticiApiGirisi } from "../yardimci";

const tema = (page: import("@playwright/test").Page) =>
  page.evaluate(() => document.documentElement.dataset.theme);

test.describe("Tema", () => {
  test("giriş sayfasında tema düğmesi temayı değiştirir ve tercih yenilemede korunur", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/giris");
    expect(await tema(page)).toBe("dark");
    const govdeKoyu = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);

    await page.getByRole("button", { name: "Açık temaya geç" }).click();
    expect(await tema(page)).toBe("light");
    expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).not.toBe(govdeKoyu);
    expect(await page.evaluate(() => localStorage.getItem("rota-tema"))).toBe("light");

    await page.reload();
    expect(await tema(page)).toBe("light");
    await expect(page.getByRole("button", { name: "Koyu temaya geç" })).toBeVisible();

    await page.getByRole("button", { name: "Koyu temaya geç" }).click();
    expect(await tema(page)).toBe("dark");
    await page.reload();
    expect(await tema(page)).toBe("dark");
  });

  test("kayıtlı tercih yoksa sistem renk şeması kullanılır", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/giris");
    expect(await tema(page)).toBe("light");
  });
});

test.describe("Bölüm alt menüsü", () => {
  test("bölüm aktif rotadan seçilir; alt menü gizlenir, göster düğmesi çıkar; menü ve tema tercihi yenilemede korunur", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await yoneticiApiGirisi(page);
    await page.goto("/ogrenciler");
    await expect(page.getByRole("heading", { name: "Öğrenciler" })).toBeVisible();

    // Şeritteki tema düğmesi de çalışır ve tercih korunur.
    expect(await tema(page)).toBe("dark");
    await page.getByRole("button", { name: "Açık temaya geç" }).click();
    expect(await tema(page)).toBe("light");
    await page.reload();
    await expect(page.getByRole("heading", { name: "Öğrenciler" })).toBeVisible();
    expect(await tema(page)).toBe("light");

    const altMenu = page.getByRole("complementary", { name: "Kayıtlar menüsü" });
    await expect(altMenu).toBeVisible();
    await expect(altMenu.getByRole("link", { name: "Öğrenciler" })).toHaveAttribute("aria-current", "page");
    await expect(altMenu.getByRole("link", { name: "Antrenörler" })).toBeVisible();
    await expect(altMenu.getByRole("link", { name: "Gruplar" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Kayıtlar" })).toHaveAttribute("aria-pressed", "true");

    await page.getByRole("button", { name: "Menüyü gizle" }).click();
    await expect(page.getByRole("complementary")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Menüyü göster" })).toBeVisible();

    await page.reload();
    await expect(page.getByRole("heading", { name: "Öğrenciler" })).toBeVisible();
    await expect(page.getByRole("complementary")).toHaveCount(0);
    expect(await page.evaluate(() => localStorage.getItem("rota-alt-menu"))).toBe("kapali");

    await page.getByRole("button", { name: "Menüyü göster" }).click();
    await expect(page.getByRole("complementary", { name: "Kayıtlar menüsü" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Menüyü göster" })).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole("complementary", { name: "Kayıtlar menüsü" })).toBeVisible();
  });

  test("bölüm şeridinden bölüm değişir; Finans ve Sistem öğeleri 'Yakında' etiketli ve tıklanamaz", async ({ page }) => {
    await yoneticiApiGirisi(page);
    await page.goto("/gruplar");
    await expect(page.getByRole("heading", { name: "Gruplar" })).toBeVisible();
    const url = page.url();

    for (const [bolum, ogeler] of [
      ["Finans", ["Ödemeler", "Paketler", "Gelir raporu"]],
      ["Sistem", ["Bildirimler", "Denetim kaydı", "Ayarlar"]],
    ] as const) {
      await page.getByRole("button", { name: bolum, exact: true }).click();
      const altMenu = page.getByRole("complementary", { name: `${bolum} menüsü` });
      await expect(altMenu).toBeVisible();
      for (const ad of ogeler) {
        const oge = altMenu.locator('[aria-disabled="true"]', { hasText: ad });
        await expect(oge).toBeVisible();
        await expect(oge).toContainText("Yakında");
        await oge.click({ force: true });
        await expect(page).toHaveURL(url);
        await expect(altMenu.getByRole("link", { name: ad })).toHaveCount(0);
      }
    }

    // Genel bölümüne geçince gerçek bağlantılar çalışır.
    await page.getByRole("button", { name: "Genel", exact: true }).click();
    await page.getByRole("complementary", { name: "Genel menüsü" }).getByRole("link", { name: "Genel bakış" }).click();
    await expect(page).toHaveURL(/\/genel-bakis$/);
    await expect(page.getByRole("heading", { name: "Genel bakış" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Genel", exact: true })).toHaveAttribute("aria-pressed", "true");
  });
});
