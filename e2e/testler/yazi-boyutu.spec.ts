import { arayuzdenGiris, expect, test, YONETICI_GIRIS, YONETICI_SIFRE } from "../yardimci";

const olcek = (page: import("@playwright/test").Page) =>
  page.evaluate(() => ({
    zoom: getComputedStyle(document.documentElement).zoom,
    degisken: document.documentElement.style.getPropertyValue("--olcek"),
    kayit: localStorage.getItem("rota-yazi-boyutu"),
    tasma: document.documentElement.scrollWidth - window.innerWidth,
  }));

test.describe("Yazı boyutu", () => {
  test("Ayarlar'da Büyük seçilir, uygulanır, yenilemede korunur ve Normal'e dönülür", async ({ page }) => {
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await page.goto("/ayarlar");
    const kart = page.locator("section").filter({ has: page.getByRole("heading", { name: "Görünüm" }) });
    await expect(kart.getByText("Bu ayar yalnızca bu cihazda geçerlidir.")).toBeVisible();
    await expect(kart.getByRole("button", { name: "Normal", exact: true })).toHaveAttribute("aria-pressed", "true");

    await kart.getByRole("button", { name: "Büyük", exact: true }).click();
    await expect(kart.getByRole("button", { name: "Büyük", exact: true })).toHaveAttribute("aria-pressed", "true");
    let o = await olcek(page);
    expect(o).toMatchObject({ zoom: "1.1", degisken: "1.1", kayit: "buyuk" });
    expect(o.tasma).toBeLessThanOrEqual(0);

    await page.reload();
    await expect(kart.getByRole("button", { name: "Büyük", exact: true })).toHaveAttribute("aria-pressed", "true");
    o = await olcek(page);
    expect(o).toMatchObject({ zoom: "1.1", degisken: "1.1", kayit: "buyuk" });
    expect(o.tasma).toBeLessThanOrEqual(0);

    // Başlıktaki "Aa" açılır penceresi de aynı ayarı değiştirir ve Escape ile kapanır.
    await page.getByRole("button", { name: "Yazı boyutu", exact: true }).click();
    const pencere = page.getByRole("dialog", { name: "Yazı boyutu" });
    await expect(pencere).toBeVisible();
    await pencere.getByRole("button", { name: "Çok büyük", exact: true }).click();
    expect((await olcek(page)).zoom).toBe("1.25");
    await page.keyboard.press("Escape");
    await expect(pencere).toBeHidden();

    await kart.getByRole("button", { name: "Normal", exact: true }).click();
    o = await olcek(page);
    expect(o).toMatchObject({ zoom: "1", kayit: "normal" });
  });
});
