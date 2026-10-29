import { arayuzdenGiris, expect, test, YONETICI_GIRIS, YONETICI_SIFRE } from "../yardimci";

test.describe("Ayarlar", () => {
  test("yönetici kulüp telefonu ve bildirim süresini değiştirir, yenileyince kalıcıdır", async ({ page }) => {
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await page.goto("/ayarlar");
    await expect(page.getByRole("heading", { name: "Ayarlar" })).toBeVisible();

    const kulup = page.locator("section").filter({ has: page.getByRole("heading", { name: "Kulüp bilgileri" }) });
    const telefon = `5${Math.floor(100000000 + Math.random() * 899999999)}`;
    await kulup.getByRole("textbox", { name: "Telefon (isteğe bağlı)" }).fill(telefon);
    await kulup.getByRole("button", { name: "Kulüp bilgilerini kaydet" }).click();
    await expect(kulup.getByRole("status")).toContainText("kaydedildi");

    const bildirim = page.locator("section").filter({ has: page.getByRole("heading", { name: "Bildirim ayarları" }) });
    await bildirim.getByLabel(/bekleme süresi/).fill("6");
    await bildirim.getByRole("button", { name: "Bildirim ayarlarını kaydet" }).click();
    await expect(bildirim.getByRole("status")).toContainText("kaydedildi");

    // Aralık dışı değer reddedilir
    await bildirim.getByLabel(/bekleme süresi/).fill("30");
    await bildirim.getByRole("button", { name: "Bildirim ayarlarını kaydet" }).click();
    await expect(bildirim.getByRole("alert")).toContainText("1 ile 15");

    await page.reload();
    await expect(page.getByRole("textbox", { name: "Telefon (isteğe bağlı)" })).toHaveValue(telefon);
    await expect(page.getByLabel(/bekleme süresi/)).toHaveValue("6");

    // Varsayılana dön (diğer testler etkilenmesin)
    await page.getByLabel(/bekleme süresi/).fill("3");
    await page.getByRole("button", { name: "Bildirim ayarlarını kaydet" }).click();
    await expect(page.getByText("Bildirim ayarları kaydedildi.")).toBeVisible();
  });

  test("Hesabım kartı giriş bilgisini ve şifre alanlarını gösterir; giriş düzenlenebilir", async ({ page }) => {
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await page.goto("/ayarlar");
    const hesap = page.locator("section").filter({ has: page.getByRole("heading", { name: "Hesabım" }) });
    await expect(hesap.getByLabel("Giriş")).toHaveValue(YONETICI_GIRIS);
    await expect(hesap.getByLabel("Giriş")).toBeEditable();
    await expect(hesap.getByLabel("Şifreniz (onay için)")).toBeVisible();
    await expect(hesap.getByRole("button", { name: "Girişi değiştir" })).toBeVisible();
    await expect(hesap.getByLabel("Mevcut şifre")).toBeVisible();
    await expect(hesap.getByLabel("Yeni şifre", { exact: true })).toBeVisible();
    await expect(hesap.getByLabel("Yeni şifre (tekrar)")).toBeVisible();
    await hesap.getByRole("button", { name: "Şifreyi değiştir" }).click();
    await expect(hesap.getByRole("alert")).toContainText("Mevcut şifrenizi girin");
  });
});
