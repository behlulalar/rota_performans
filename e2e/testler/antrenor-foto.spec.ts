import { arayuzdenGiris, expect, KUCUK_PNG, telefonBosluklu, test, yoklamaOrtamiKur, yoneticiApiGirisi, YONETICI_GIRIS, YONETICI_SIFRE, zorunluSifreyiBelirle } from "../yardimci";

test.describe("Antrenör fotoğrafı", () => {
  test("yönetici onayla yükler; antrenör kendi fotoğrafını görür ama değiştiremez; veli çocuğunun antrenörünü görür", async ({ page }) => {
    // Üç farklı hesapla giriş: hız sınırı beklemesi gerekebilir.
    test.slow();
    const o = await yoklamaOrtamiKur(page);

    // Yönetici: düzenleme penceresinden, onay kutusu işaretlenince yükler.
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await expect(page).toHaveURL(/\/genel-bakis$/);
    await page.goto("/antrenorler");
    const satir = page.getByRole("row").filter({ hasText: o.antrenor.adSoyad });
    await satir.getByRole("button", { name: "Düzenle" }).click();
    const pencere = page.getByRole("dialog", { name: "Antrenörü düzenle" });
    await expect(pencere.getByRole("button", { name: "Fotoğraf ekle" })).toBeDisabled();
    await pencere.getByLabel("Antrenörün fotoğraf kullanımı için onayı alındı").check();
    await expect(pencere.getByRole("button", { name: "Fotoğraf ekle" })).toBeEnabled();
    await pencere.getByTestId("antrenor-foto-dosya").setInputFiles({ name: "foto.png", mimeType: "image/png", buffer: KUCUK_PNG });
    const kirpma = page.getByRole("dialog", { name: "Fotoğrafı ayarla" });
    await expect(kirpma).toBeVisible();
    await kirpma.getByRole("slider", { name: "Yakınlaştırma" }).fill("2");
    await kirpma.getByRole("button", { name: "Kaydet" }).click();
    await expect(kirpma).toBeHidden();
    await expect(pencere.getByRole("img", { name: o.antrenor.adSoyad })).toBeVisible();
    await expect(pencere.getByRole("button", { name: "Değiştir" })).toBeVisible();
    await pencere.getByRole("button", { name: "Kapat" }).click();
    await expect(satir.getByRole("img", { name: o.antrenor.adSoyad })).toBeVisible();

    // Antrenör: üst çubukta ve Profilim'de kendi fotoğrafı; yükleme denetimi yok.
    await page.getByRole("button", { name: "Çıkış" }).click();
    await arayuzdenGiris(page, o.antrenor.giris, o.antrenor.sifre);
    await expect(page).toHaveURL(/\/bugun$/);
    await expect(page.getByRole("banner").getByRole("img", { name: o.antrenor.adSoyad })).toBeVisible();
    await page.goto("/profilim");
    await expect(page.getByRole("img", { name: o.antrenor.adSoyad }).first()).toBeVisible();
    await expect(page.locator('input[type="file"]')).toHaveCount(0);
    await expect(page.getByRole("button", { name: /^(Fotoğraf ekle|Değiştir|Ayarla)$/ })).toHaveCount(0);

    // Veli: çocuğunun sayfasında "Antrenörü" bloğu (ad + fotoğraf).
    const token = await yoneticiApiGirisi(page);
    const h = await page.request.post(`/api/ogrenciler/${o.geldi.id}/hesap`, { headers: { Authorization: `Bearer ${token}` }, data: {} });
    expect(h.status(), await h.text()).toBe(200);
    const gecici = ((await h.json()) as { gecici_sifre: string }).gecici_sifre;
    await page.context().clearCookies();
    await arayuzdenGiris(page, telefonBosluklu(o.geldi.telefon), gecici);
    await zorunluSifreyiBelirle(page, gecici);
    await expect(page).toHaveURL(/\/panel\/cocuk\//);
    const blok = page.getByTestId("veli-antrenor");
    await expect(blok).toHaveCount(1);
    await expect(blok).toContainText(o.antrenor.adSoyad);
    await expect(blok.getByRole("img", { name: o.antrenor.adSoyad })).toBeVisible();
    await expect(blok).not.toContainText(/\+?90\d{10}|0?5\d{9}/);
  });
});
