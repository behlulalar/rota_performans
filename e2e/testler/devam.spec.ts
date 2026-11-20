import { arayuzdenGiris, expect, test, yoklamaOrtamiKur, YONETICI_GIRIS, YONETICI_SIFRE } from "../yardimci";

test.describe("Devam özeti", () => {
  test("antrenör yoklama alır, Öğrencilerim'de ve yönetici öğrenci/grup sayfasında devam özetini görür", async ({ page }) => {
    test.slow();
    const o = await yoklamaOrtamiKur(page);
    const klasor = process.env.EKRAN_KLASORU;

    await arayuzdenGiris(page, o.antrenor.giris, o.antrenor.sifre);
    await page.getByRole("navigation", { name: "Ana menü" }).getByRole("link", { name: "Takvim" }).click();
    await page.getByRole("link", { name: new RegExp(o.grupAdi) }).click();
    const satir = (ad: string) => page.getByRole("listitem", { name: new RegExp(ad) });
    await satir(o.geldi.ad).getByRole("button", { name: "Geldi", exact: true }).click();
    await satir(o.gelmedi.ad).getByRole("button", { name: "Gelmedi", exact: true }).click();
    await satir(o.gelmedi.ad).getByRole("button", { name: "Raporlu", exact: true }).click();
    await page.getByRole("button", { name: "Yoklamayı kaydet (2/2 işaretli)" }).click();
    const ozet = page.getByRole("dialog", { name: "Yoklama kaydedildi" });
    await expect(ozet).toBeVisible();
    await ozet.getByRole("button", { name: "Tamam" }).click();
    await expect(ozet).toHaveCount(0);

    // Antrenör: Öğrencilerim
    await page.getByRole("navigation", { name: "Ana menü" }).getByRole("link", { name: "Öğrencilerim" }).click();
    await expect(page).toHaveURL(/\/ogrencilerim$/);
    const grup = page.locator("section").filter({ has: page.getByRole("heading", { name: o.grupAdi }) });
    await expect(grup.getByRole("listitem").filter({ hasText: o.geldi.ad })).toContainText("%100");
    await expect(grup.getByRole("listitem").filter({ hasText: o.gelmedi.ad })).toContainText("%0");
    if (klasor) {
      for (const [ad, en, boy] of [["masaustu", 1280, 800], ["telefon", 390, 844]] as const) {
        await page.setViewportSize({ width: en, height: boy });
        await page.screenshot({ path: `${klasor}/devam-antrenor-${ad}.png`, fullPage: true });
      }
      await page.setViewportSize({ width: 1280, height: 800 });
    }

    // Yönetici: öğrenci sayfası ve grup sayfası
    await page.getByRole("button", { name: "Çıkış" }).click();
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await page.goto(`/ogrenciler/${o.gelmedi.id}`);
    const kart = page.locator("section").filter({ has: page.getByRole("heading", { name: "Devam özeti" }) });
    await expect(kart.getByText("Son 30 gün")).toBeVisible();
    await expect(kart.getByText("0 geldi · 1 gelmedi").first()).toBeVisible();
    if (klasor) await kart.screenshot({ path: `${klasor}/devam-ogrenci.png` });

    await page.goto("/gruplar");
    await page.getByRole("link", { name: o.grupAdi }).first().click();
    const liste = page.locator("section").filter({ has: page.getByRole("heading", { name: /^Öğrenciler/ }) });
    await expect(liste.getByRole("listitem").filter({ hasText: o.geldi.ad })).toContainText("%100");
    if (klasor) await liste.screenshot({ path: `${klasor}/devam-grup.png` });
  });
});
