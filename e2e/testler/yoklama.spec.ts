import { arayuzdenGiris, expect, test, yoklamaOrtamiKur, YONETICI_GIRIS, YONETICI_SIFRE } from "../yardimci";

test.describe("Yoklama", () => {
  test("antrenör takvimden oturumu açar, yoklamayı alır; yönetici bakiyeyi düşmüş görür", async ({ page }) => {
    // Giriş hız sınırı beklemesi (20 sn) gerekebilir; süre üç katına çıkar.
    test.slow();
    const o = await yoklamaOrtamiKur(page);

    await arayuzdenGiris(page, o.antrenor.giris, o.antrenor.sifre);
    await expect(page).toHaveURL(/\/bugun$/);
    await expect(page.getByRole("link", { name: "Öğrenciler", exact: true })).toHaveCount(0);
    await page.getByRole("navigation", { name: "Ana menü" }).getByRole("link", { name: "Takvim" }).click();
    await expect(page).toHaveURL(/\/takvim$/);

    const kart = page.getByRole("link", { name: new RegExp(o.grupAdi) });
    await expect(kart).toBeVisible();
    await expect(kart).toContainText("2 öğrenci");
    await kart.click();

    await expect(page).toHaveURL(/\/oturum\/[0-9a-f-]{36}$/);
    await expect(page.getByRole("heading", { name: o.grupAdi })).toBeVisible();
    const satir = (ad: string) => page.getByRole("listitem", { name: new RegExp(ad) });
    await satir(o.geldi.ad).getByRole("button", { name: "Geldi", exact: true }).click();
    await satir(o.gelmedi.ad).getByRole("button", { name: "Gelmedi", exact: true }).click();
    await satir(o.gelmedi.ad).getByRole("button", { name: "Raporlu", exact: true }).click();
    await page.getByRole("button", { name: "Yoklamayı kaydet (2/2 işaretli)" }).click();

    const ozet = page.getByRole("dialog", { name: "Yoklama kaydedildi" });
    await expect(ozet).toBeVisible();
    await expect(ozet).toContainText("Geldi: 1");
    await expect(ozet).toContainText("Gelmedi: 1 (Raporlu: 1)");
    await expect(ozet).not.toContainText("işaretlenmedi");
    await expect(ozet).toContainText("Gelmedi işaretlemeleri 1 saat içinde düzeltilebilir.");
    await expect(ozet.getByRole("button", { name: "Tamam" })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(ozet).toHaveCount(0);
    await expect(page.getByText("Yoklama alındı")).toBeVisible();
    await expect(satir(o.geldi.ad).getByRole("button", { name: "Geldi", exact: true })).toHaveAttribute("aria-pressed", "true");

    await page.getByRole("link", { name: "← Takvim" }).click();
    await expect(page.getByRole("link", { name: new RegExp(o.grupAdi) })).toContainText("Yoklama alındı");

    // Yönetici: paket yüklenmeden geldi olan öğrencinin kalan dersi 0 görünür, fazla işlenen ders kırmızı notla bildirilir.
    await page.getByRole("button", { name: "Çıkış" }).click();
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await expect(page).toHaveURL(/\/genel-bakis$/);
    await page.goto(`/ogrenciler/${o.geldi.id}`);
    await expect(page.getByText("Kalan ders").locator("xpath=following-sibling::div")).toHaveText("0");
    await expect(page.getByText("Ders hakkı bitti: paketle yüklenenden 1 ders fazla işlendi")).toBeVisible();
  });
});
