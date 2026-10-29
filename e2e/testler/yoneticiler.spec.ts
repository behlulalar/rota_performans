import { arayuzdenGiris, benzersiz, expect, test, YENI_SIFRE, yoneticiApiGirisi, zorunluSifreyiBelirle } from "../yardimci";

test.describe("Yöneticiler", () => {
  test("yeni yönetici oluşturulur, girer, kendi girişini değiştirir ve yeni girişle girer", async ({ page }) => {
    await yoneticiApiGirisi(page);
    const k = benzersiz();
    const adSoyad = `Yonetici ${k}`;
    const giris = `yonetici.${k}@example.com`;
    const yeniGiris = `yonetici.yeni.${k}@example.com`;

    await page.goto("/yoneticiler");
    await expect(page.getByRole("heading", { name: "Yöneticiler", level: 1 })).toBeVisible();
    await expect(page.getByRole("link", { name: "Yöneticiler" })).toBeVisible();
    // Kendi satırı: "(siz)" ve pasife alma / şifre sıfırlama kapalı
    const kendi = page.getByRole("row", { name: /\(siz\)/ });
    await expect(kendi.getByRole("button", { name: "Pasife al" })).toBeDisabled();
    await expect(kendi.getByRole("button", { name: "Şifre sıfırla" })).toBeDisabled();

    await page.getByRole("button", { name: "Yeni yönetici" }).click();
    const form = page.getByRole("dialog", { name: "Yeni yönetici" });
    await form.getByLabel("Ad soyad").fill(adSoyad);
    await form.getByLabel(/Giriş \(e-posta/).fill(giris);
    await form.getByRole("button", { name: "Oluştur" }).click();

    const sifreKutusu = page.getByRole("dialog", { name: `${adSoyad} için geçici şifre` });
    await expect(sifreKutusu).toBeVisible();
    const gecici = (await sifreKutusu.locator("code").innerText()).trim();
    expect(gecici.length).toBeGreaterThanOrEqual(8);
    await sifreKutusu.getByRole("button", { name: "Kapat" }).click();
    await expect(page.getByRole("row", { name: new RegExp(adSoyad) })).toBeVisible();

    // Aynı girişle ikinci kayıt reddedilir
    await page.getByRole("button", { name: "Yeni yönetici" }).click();
    const form2 = page.getByRole("dialog", { name: "Yeni yönetici" });
    await form2.getByLabel("Ad soyad").fill("Baska Kisi");
    await form2.getByLabel(/Giriş \(e-posta/).fill(giris);
    await form2.getByRole("button", { name: "Oluştur" }).click();
    await expect(form2.getByRole("alert")).toContainText("başka bir hesapta kayıtlı");
    await form2.getByRole("button", { name: "Kapat" }).click();

    // Yeni yönetici girer ve şifresini belirler
    await page.getByRole("button", { name: "Çıkış" }).click();
    await expect(page).toHaveURL(/\/yonetici-giris$/);
    await arayuzdenGiris(page, giris, gecici, "yonetici");
    await zorunluSifreyiBelirle(page, gecici);
    await expect(page.getByRole("heading", { name: "Genel bakış", level: 1 })).toBeVisible();

    // Ayarlar > Hesabım: yanlış şifreyle değişmez, doğru şifreyle değişir
    await page.goto("/ayarlar");
    const hesap = page;
    await expect(page.getByText("Hesabım", { exact: true })).toBeVisible();
    const girisKutusu = hesap.getByLabel(/^Giriş \(e-posta/);
    await expect(girisKutusu).toHaveValue(giris);
    await girisKutusu.fill(yeniGiris);
    await hesap.getByLabel("Şifreniz (onay için)").fill("yanlis-sifre-999");
    await hesap.getByRole("button", { name: "Girişi değiştir" }).click();
    await expect(hesap.getByRole("alert").filter({ hasText: /./ })).toContainText("Şifre hatalı");
    await hesap.getByLabel("Şifreniz (onay için)").fill(YENI_SIFRE);
    await hesap.getByRole("button", { name: "Girişi değiştir" }).click();
    await expect(hesap.getByRole("status")).toContainText("Giriş bilginiz değiştirildi");
    await expect(girisKutusu).toHaveValue(yeniGiris);

    // Oturum açık kalır; çıkıp yeni girişle girilir, eskisiyle girilemez
    await page.getByRole("button", { name: "Çıkış" }).click();
    await arayuzdenGiris(page, giris, YENI_SIFRE, "yonetici");
    await expect(page.getByRole("alert")).toBeVisible();
    await arayuzdenGiris(page, yeniGiris, YENI_SIFRE, "yonetici");
    await expect(page.getByRole("heading", { name: "Genel bakış", level: 1 })).toBeVisible();
    await page.goto("/yoneticiler");
    await expect(page.getByRole("row", { name: new RegExp(`${adSoyad}.*\\(siz\\)`) })).toBeVisible();
  });

  test("yönetici, antrenörün girişini değiştirir", async ({ page }) => {
    const belirtec = await yoneticiApiGirisi(page);
    const k = benzersiz();
    const giris = `antrenor.${k}@example.com`;
    const yeniGiris = `antrenor.yeni.${k}@example.com`;
    const yanit = await page.request.post("/api/antrenorler", {
      headers: { Authorization: `Bearer ${belirtec}` },
      data: { ad_soyad: `Antrenor ${k}`, giris },
    });
    expect(yanit.status()).toBe(201);
    const gecici = ((await yanit.json()) as { gecici_sifre: string }).gecici_sifre;

    await page.goto("/antrenorler");
    await page.getByRole("row", { name: new RegExp(`Antrenor ${k}`) }).getByRole("button", { name: "Düzenle" }).click();
    const modal = page.getByRole("dialog", { name: "Antrenörü düzenle" });
    await modal.getByLabel(/^Giriş \(e-posta/).fill(yeniGiris);
    await modal.getByRole("button", { name: "Kaydet" }).click();
    await expect(page.getByRole("row", { name: new RegExp(yeniGiris.replace(/\./g, "\\.")) })).toBeVisible();

    await page.getByRole("button", { name: "Çıkış" }).click();
    await arayuzdenGiris(page, yeniGiris, gecici, "antrenor");
    await zorunluSifreyiBelirle(page, gecici);
    await expect(page).toHaveURL(/\/bugun$/);
  });
});
