import { arayuzdenGiris, expect, ogrenciOlusturAPI, telefonBosluklu, test, YONETICI_GIRIS, YONETICI_SIFRE, yoneticiApiGirisi } from "../yardimci";

test.describe("Giriş", () => {
  test("yanlış şifre hata mesajı gösterir ve giriş yapılmaz", async ({ page }) => {
    await arayuzdenGiris(page, YONETICI_GIRIS, "tamamen-yanlis-sifre");
    await expect(page.getByRole("alert")).toContainText("Giriş bilgileri hatalı");
    await expect(page).toHaveURL(/\/yonetici-giris$/);
  });

  test("doğru şifre yöneticiyi genel bakışa yönlendirir, çıkış giriş sayfasına döner", async ({ page }) => {
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await expect(page).toHaveURL(/\/genel-bakis$/);
    await expect(page.getByRole("heading", { name: "Genel bakış" })).toBeVisible();

    await page.getByRole("button", { name: "Çıkış" }).click();
    await expect(page).toHaveURL(/\/yonetici-giris$/);

    // Çıkıştan sonra korumalı sayfa tekrar girişe yönlendirir.
    await page.goto("/ogrenciler");
    await expect(page).toHaveURL(/\/yonetici-giris$/);
  });

  test("her rolün kendi giriş sayfası var; yanlış panelden doğru şifreyle bile girilemez", async ({ page }) => {
    await page.goto("/giris");
    await expect(page.getByRole("heading", { name: "Veli / öğrenci girişi" })).toBeVisible();
    await page.goto("/antrenor-giris");
    await expect(page.getByRole("heading", { name: "Antrenör girişi" })).toBeVisible();
    await page.goto("/yonetici-giris");
    await expect(page.getByRole("heading", { name: "Yönetici girişi" })).toBeVisible();

    // Yönetici, veli girişinden ve antrenör girişinden giremez.
    for (const panel of ["veli", "antrenor"] as const) {
      await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE, panel);
      await expect(page.getByRole("alert")).toContainText("Giriş bilgileri hatalı");
      await expect(page).not.toHaveURL(/genel-bakis/);
    }
  });

  test("korumalı yönetici sayfası yönetici girişine, kök adres veli girişine yönlendirir", async ({ page }) => {
    await page.goto("/ogrenciler");
    await expect(page).toHaveURL(/\/yonetici-giris$/);
    await page.goto("/");
    await expect(page).toHaveURL(/\/giris$/);
  });

  test("yönetici açıkken veli giriş adresi formu gösterir; veli hesabıyla girince oturum değişir", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const ogr = await ogrenciOlusturAPI(page, token, "Gecis");
    const h = await page.request.post(`/api/ogrenciler/${ogr.id}/hesap`, { headers: { Authorization: `Bearer ${token}` }, data: {} });
    const gecici = ((await h.json()) as { gecici_sifre: string }).gecici_sifre;

    await page.goto("/genel-bakis");
    await expect(page.getByRole("heading", { name: "Genel bakış" })).toBeVisible();
    await page.goto("/giris");
    await expect(page.getByRole("heading", { name: "Veli / öğrenci girişi" })).toBeVisible();
    await expect(page.getByLabel("Telefon veya e-posta")).toBeVisible();

    await arayuzdenGiris(page, telefonBosluklu(ogr.telefon), gecici);
    await expect(page).toHaveURL(/\/sifre-degistir$/);
  });
});
