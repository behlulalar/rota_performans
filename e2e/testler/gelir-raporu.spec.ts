import {
  arayuzdenGiris, expect, gelirRaporuAPI, odemeAlAPI, ogrenciOlusturAPI, paketAtaAPI, paketOlusturAPI, test,
  yoneticiApiGirisi, YONETICI_GIRIS, YONETICI_SIFRE,
} from "../yardimci";

const para = (d: string) => `${Number(d).toLocaleString("tr-TR", { minimumFractionDigits: Number(d) % 1 === 0 ? 0 : 2, maximumFractionDigits: Number(d) % 1 === 0 ? 0 : 2 })} ₺`;

test.describe("Gelir raporu", () => {
  test("ödeme alınca toplam ve yöntem dağılımı görünür; ay geri gidilir; CSV iner; menü bağlantısı çalışır", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const simdi = new Date();
    const yil = simdi.getFullYear();
    const ay = simdi.getMonth() + 1;
    const onceki = new Date(yil, ay - 2, 1);

    const ogr = await ogrenciOlusturAPI(page, token, "Gelir");
    const paket = await paketOlusturAPI(page, token, { ders_sayisi: 8, fiyat: "3400" });
    const opId = await paketAtaAPI(page, token, ogr.id, paket.id);
    await odemeAlAPI(page, token, opId, "nakit");

    const buAy = await gelirRaporuAPI(page, token, yil, ay);
    const oncekiAy = await gelirRaporuAPI(page, token, onceki.getFullYear(), onceki.getMonth() + 1);
    expect(Number(buAy.ozet.toplam_tahsilat)).toBeGreaterThanOrEqual(3400);

    await page.context().clearCookies();
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await expect(page).toHaveURL(/\/genel-bakis$/);

    // Menüden
    await page.getByRole("complementary", { name: "Menü" }).getByRole("link", { name: "Gelir raporu" }).click();
    await expect(page).toHaveURL(/\/gelir-raporu$/);
    await expect(page.getByRole("heading", { name: "Gelir raporu" })).toBeVisible();

    await expect(page.getByTestId("kpi-tahsilat")).toContainText(para(buAy.ozet.toplam_tahsilat));
    await expect(page.getByTestId("kpi-adet")).toContainText(String(buAy.ozet.odeme_adedi));
    await expect(page.getByTestId("yontem-dagilimi")).toContainText("Nakit");
    await expect(page.getByTestId("paket-dagilimi")).toContainText(paket.ad);
    await expect(page.getByRole("button", { name: "Sonraki ay" })).toBeDisabled();
    await expect(page.getByRole("table", { name: "Son 12 ay tahsilat tablosu" })).toHaveCount(1);

    // CSV
    const [indirme] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "CSV indir (seçili ay)" }).click(),
    ]);
    expect(indirme.suggestedFilename()).toMatch(/^gelir-.*\.csv$/);

    // Ay geri
    await page.getByRole("button", { name: "Önceki ay" }).click();
    await expect(page.getByTestId("donem-adi")).toContainText(String(onceki.getFullYear()));
    if (Number(oncekiAy.ozet.odeme_adedi) === 0) {
      await expect(page.getByText("Bu ayda tahsilat yok")).toBeVisible();
    } else {
      await expect(page.getByTestId("kpi-tahsilat")).toContainText(para(oncekiAy.ozet.toplam_tahsilat));
    }
    await expect(page.getByRole("button", { name: "Sonraki ay" })).toBeEnabled();
    // 12 aylık grafikte seçili ay (önceki ay) vurgulu ve sonu odur; bir aya tıklayınca o aya geçilir.
    const ad = (d: Date) => d.toLocaleDateString("tr-TR", { month: "long", year: "numeric" });
    await expect(page.getByRole("button", { name: new RegExp(`^${ad(onceki)}:`, "i") })).toHaveAttribute("aria-pressed", "true");
    const dahaOnce = new Date(onceki.getFullYear(), onceki.getMonth() - 1, 1);
    await page.getByRole("button", { name: new RegExp(`^${ad(dahaOnce)}:`, "i") }).click();
    await expect(page.getByTestId("donem-adi")).toHaveText(ad(dahaOnce), { ignoreCase: true });
    // İleri gidince geçerli ay yeniden toplamı gösterir.
    await page.getByRole("button", { name: "Sonraki ay" }).click();
    await page.getByRole("button", { name: "Sonraki ay" }).click();
    await expect(page.getByTestId("kpi-tahsilat")).toContainText(para(buAy.ozet.toplam_tahsilat));
  });
});
