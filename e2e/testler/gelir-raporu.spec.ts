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
    await expect(page.getByRole("table", { name: "Son 12 ay net gelir tablosu" })).toHaveCount(1);

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
      await expect(page.getByText("Bu ayda tahsilat veya manuel kayıt yok")).toBeVisible();
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
  test("yönetici manuel gelir ve gider ekler, net gelire yansır; kaydı iptal eder", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const simdi = new Date();
    const onceki = await gelirRaporuAPI(page, token, simdi.getFullYear(), simdi.getMonth() + 1);
    const netOnce = Number(onceki.ozet.net_gelir);

    await page.context().clearCookies();
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await page.goto("/gelir-raporu");
    const kart = page.locator("section").filter({ has: page.getByRole("heading", { name: "Manuel gelir ve giderler" }) });
    const aciklama = `Yaz kampı ${Date.now()}`;

    await kart.getByRole("button", { name: "Kayıt ekle" }).click();
    await kart.getByLabel("Tutar (₺)").fill("2000");
    await kart.getByLabel("Açıklama").fill(aciklama);
    await kart.getByRole("button", { name: "Geliri kaydet" }).click();
    await expect(kart.getByRole("listitem").filter({ hasText: aciklama })).toContainText("+2.000 ₺");

    await kart.getByRole("button", { name: "Kayıt ekle" }).click();
    await kart.getByRole("button", { name: "− Gider" }).click();
    await kart.getByLabel("Tutar (₺)").fill("1500");
    await kart.getByLabel("Yöntem").selectOption("havale_eft");
    await kart.getByLabel("Açıklama").fill(`Havuz kirası ${aciklama}`);
    await kart.getByRole("button", { name: "Gideri kaydet" }).click();
    await expect(kart.getByRole("listitem").filter({ hasText: "Havuz kirası" })).toContainText("−1.500 ₺");
    await expect(page.getByTestId("kpi-net")).toContainText(para(String(netOnce + 500)));
    const klasor = process.env.EKRAN_KLASORU;
    if (klasor) {
      await page.getByTestId("kpi-net").screenshot({ path: `${klasor}/manuel-net.png` });
      await kart.screenshot({ path: `${klasor}/manuel-kart.png` });
      await page.setViewportSize({ width: 390, height: 844 });
      await page.screenshot({ path: `${klasor}/manuel-telefon.png`, fullPage: true });
      await page.setViewportSize({ width: 1280, height: 800 });
    }

    const satir = kart.getByRole("listitem").filter({ hasText: aciklama }).filter({ hasNotText: "Havuz" });
    await satir.getByRole("button", { name: "İptal et" }).click();
    await satir.getByLabel("İptal nedeni").fill("Yanlış girildi");
    await satir.getByRole("button", { name: "Kaydı iptal et" }).click();
    await expect(satir).toContainText("İptal: Yanlış girildi");
    await expect(page.getByTestId("kpi-net")).toContainText(para(String(netOnce - 1500)));
  });

  test("yıllık ve günlük kapsam: seçiciler çalışır, gelecek kapatılır, ay çubuğu aya geçirir", async ({ page }) => {
    await yoneticiApiGirisi(page);
    await page.goto("/gelir-raporu");
    const simdi = new Date();
    const donemAdi = page.getByTestId("donem-adi");
    await expect(page.getByRole("button", { name: "Aylık" })).toHaveAttribute("aria-pressed", "true");

    // Yıllık: yıl adı görünür, gelecek yıla gidilemez, önceki yıl çalışır; 12 aylık grafik o yılın aylarını gösterir.
    await page.getByRole("button", { name: "Yıllık" }).click();
    await expect(donemAdi).toHaveText(String(simdi.getFullYear()));
    await expect(page.getByRole("button", { name: "Sonraki yıl" })).toBeDisabled();
    await expect(page.getByRole("heading", { name: `${simdi.getFullYear()} yılı aylara göre net gelir` })).toBeVisible();
    await expect(page.getByRole("button", { name: "CSV indir (seçili yıl)" })).toBeVisible();
    await page.getByRole("button", { name: "Önceki yıl" }).click();
    await expect(donemAdi).toHaveText(String(simdi.getFullYear() - 1));
    await expect(page.getByRole("button", { name: "Sonraki yıl" })).toBeEnabled();
    await page.getByLabel("Yıl seç").selectOption(String(simdi.getFullYear()));
    await expect(donemAdi).toHaveText(String(simdi.getFullYear()));

    // Yıllıkta bir aya tıklayınca Aylık kapsama geçilir.
    await page.getByRole("button", { name: /^Ocak /i }).click();
    await expect(page.getByRole("button", { name: "Aylık" })).toHaveAttribute("aria-pressed", "true");
    await expect(donemAdi).toContainText(`Ocak ${simdi.getFullYear()}`);

    // Günlük: tarih seçici bugünü gösterir, bugünden ilerisi seçilemez, bir gün geri gidilir.
    await page.getByRole("button", { name: "Günlük" }).click();
    const gun = page.getByLabel("Gün seç");
    const yyyyAyGun = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    await expect(gun).toHaveAttribute("max", yyyyAyGun(simdi));
    await page.getByLabel("Gün seç").fill("2026-03-10");
    await expect(donemAdi).toHaveText("10 Mart 2026");
    await expect(page.getByRole("button", { name: "CSV indir (seçili gün)" })).toBeVisible();
    await page.getByRole("button", { name: "Önceki gün" }).click();
    await expect(donemAdi).toHaveText("9 Mart 2026");
    await expect(page.getByTestId("kpi-net")).toBeVisible();
    // Aylığa dönünce günün ayı açılır.
    await page.getByRole("button", { name: "Aylık" }).click();
    await expect(donemAdi).toHaveText("Mart 2026", { ignoreCase: true });
  });
});
