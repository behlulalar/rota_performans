import { YONETICI_GIRIS, YONETICI_SIFRE, arayuzdenGiris, expect, telefonBosluklu, test, yoklamaOrtamiKur, yoneticiApiGirisi, zorunluSifreyiBelirle } from "../yardimci";

test.describe("Devamsızlık sebebi", () => {
  test("sebepsiz kayıt engellenir; Raporlu + açıklama kaydedilir; veli sebebi görür, açıklamayı görmez", async ({ page }) => {
    test.slow();
    const o = await yoklamaOrtamiKur(page);
    const AciklamaMetni = `Doktor raporu gizli not ${Date.now()}`;

    // Yönetici: gelmedi öğrenciye veli hesabı aç (antrenör girişinden önce, belirteç çerezleri silinmeden).
    const token = await yoneticiApiGirisi(page);
    const h = await page.request.post(`/api/ogrenciler/${o.gelmedi.id}/hesap`, { headers: { Authorization: `Bearer ${token}` }, data: {} });
    expect(h.status(), await h.text()).toBe(200);
    const gecici = ((await h.json()) as { gecici_sifre: string }).gecici_sifre;
    await page.context().clearCookies();

    await arayuzdenGiris(page, o.antrenor.giris, o.antrenor.sifre);
    await page.getByRole("navigation", { name: "Ana menü" }).getByRole("link", { name: "Takvim" }).click();
    await page.getByRole("link", { name: new RegExp(o.grupAdi) }).click();
    const satir = (ad: string) => page.getByRole("listitem", { name: new RegExp(ad) });

    await satir(o.geldi.ad).getByRole("button", { name: "Geldi", exact: true }).click();
    await satir(o.gelmedi.ad).getByRole("button", { name: "Gelmedi", exact: true }).click();
    const sebepAlani = satir(o.gelmedi.ad).getByRole("group", { name: "Devamsızlık sebebi" });
    await expect(sebepAlani.getByRole("button")).toHaveCount(4);

    // Sebepsiz kayıt engellenir.
    await page.getByRole("button", { name: /Yoklamayı kaydet/ }).click();
    await expect(page.getByRole("alert").filter({ hasText: "devamsızlık sebebi seçilmeli" }).first()).toBeVisible();
    await expect(satir(o.gelmedi.ad)).toHaveAttribute("data-eksik", "true");
    await expect(page.getByText("Yoklama alındı")).toHaveCount(0);

    // Raporlu + açıklama.
    await sebepAlani.getByRole("button", { name: "Raporlu", exact: true }).click();
    await expect(satir(o.gelmedi.ad)).not.toHaveAttribute("data-eksik", "true");
    await expect(satir(o.gelmedi.ad).getByText("Telafi bu ay içinde planlanmalı")).toBeVisible();
    await satir(o.gelmedi.ad).getByRole("button", { name: "+ Açıklama ekle" }).click();
    await satir(o.gelmedi.ad).getByRole("textbox").fill(AciklamaMetni);
    await page.getByRole("button", { name: /Yoklamayı kaydet/ }).click();
    await expect(page.getByRole("status")).toContainText("Yoklama kaydedildi");

    // Kayıtlı sebep ve açıklama yeniden açılınca görünür.
    await page.reload();
    await expect(satir(o.gelmedi.ad).getByRole("button", { name: "Raporlu", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(satir(o.gelmedi.ad).getByRole("textbox")).toHaveValue(AciklamaMetni);

    // Geldi'ye dönmek sebep alanını kaldırır.
    await satir(o.gelmedi.ad).getByRole("button", { name: "Geldi", exact: true }).click();
    await expect(satir(o.gelmedi.ad).getByTestId("sebep-alani")).toHaveCount(0);

    // Veli: sebebi görür, açıklamayı görmez.
    await page.getByRole("button", { name: "Çıkış" }).click();
    await arayuzdenGiris(page, telefonBosluklu(o.gelmedi.telefon), gecici);
    await zorunluSifreyiBelirle(page, gecici);
    await expect(page).toHaveURL(/\/panel\/cocuk\//);
    // Bugünkü ders henüz "yaklaşan" listesindedir (gün bitmedi); gelmedi etiketi orada görünür.
    await expect(page.getByText("Gelmedi · Raporlu")).toBeVisible();
    await expect(page.getByText(AciklamaMetni)).toHaveCount(0);
    expect(await page.content()).not.toContain(AciklamaMetni);

    // Yönetici: öğrenci sayfasındaki devam özeti açıklamayı sebep rozetinin altında gösterir.
    await page.context().clearCookies();
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await page.emulateMedia({ colorScheme: "dark" });
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(`/ogrenciler/${o.gelmedi.id}`);
    const kart = page.locator("section").filter({ has: page.getByRole("heading", { name: "Devam özeti" }) });
    await expect(kart.getByTestId("devamsizlik-aciklama")).toHaveText(AciklamaMetni);
    const klasor = process.env.EKRAN_KLASORU;
    if (klasor) await kart.screenshot({ path: `${klasor}/admin-aciklama.png` });
  });
});
