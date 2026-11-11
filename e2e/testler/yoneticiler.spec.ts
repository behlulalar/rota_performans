import { arayuzdenGiris, benzersiz, expect, telefonBosluklu, telefonGorunen, telefonUret10, test, YENI_SIFRE, yeniAntrenorGirisi, yoneticiApiGirisi, zorunluSifreyiBelirle } from "../yardimci";

test.describe("Yöneticiler", () => {
  test("yeni yönetici oluşturulur, girer, kendi girişini değiştirir ve yeni girişle girer", async ({ page }) => {
    await yoneticiApiGirisi(page);
    const k = benzersiz();
    const adSoyad = `Yonetici ${k}`;
    const giris = `+90${telefonUret10()}`;
    const yeniGiris = `+90${telefonUret10()}`;

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

  test("e-posta girişli yönetici telefonla da girer ve kendi telefonunu değiştirir", async ({ page }) => {
    await yoneticiApiGirisi(page);
    const k = benzersiz();
    const adSoyad = `Telefonlu ${k}`;
    const giris = `telefonlu.${k}@example.com`;
    const on = telefonUret10();
    const tel = `+90${on}`;

    await page.goto("/yoneticiler");
    await page.getByRole("button", { name: "Yeni yönetici" }).click();
    const form = page.getByRole("dialog", { name: "Yeni yönetici" });
    await form.getByLabel("Ad soyad").fill(adSoyad);
    await form.getByLabel(/Giriş \(e-posta/).fill(giris);
    await form.getByLabel(/^Telefon/).fill(on);
    await form.getByRole("button", { name: "Oluştur" }).click();
    const sifreKutusu = page.getByRole("dialog", { name: `${adSoyad} için geçici şifre` });
    const gecici = (await sifreKutusu.locator("code").innerText()).trim();
    // Giriş e-posta olduğu için WhatsApp mesajı telefon alanındaki numaraya gider
    await expect(sifreKutusu.getByRole("link", { name: /WhatsApp/ })).toHaveAttribute("href", new RegExp(`wa\\.me/90${on}`));
    await sifreKutusu.getByRole("button", { name: "Kapat" }).click();
    await expect(page.getByRole("row", { name: new RegExp(adSoyad) })).toContainText(telefonGorunen(tel));

    // Çıkış; telefonla (boşluklu biçim) yönetici girişi
    await page.getByRole("button", { name: "Çıkış" }).click();
    const bosluklu = telefonBosluklu(tel);
    await arayuzdenGiris(page, bosluklu, gecici, "yonetici");
    await zorunluSifreyiBelirle(page, gecici);
    await expect(page.getByRole("heading", { name: "Genel bakış", level: 1 })).toBeVisible();

    // Ayarlar > Hesabım: kendi telefonunu değiştirir
    await page.goto("/ayarlar");
    const yeniOn = telefonUret10();
    const telKutusu = page.getByLabel("Telefon numaram");
    await expect(telKutusu).toHaveValue(on);
    await telKutusu.fill(yeniOn);
    await page.getByLabel("Şifreniz (telefon onayı için)").fill("yanlis-sifre-999");
    await page.getByRole("button", { name: "Telefonu kaydet" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Şifre hatalı" })).toBeVisible();
    await page.getByLabel("Şifreniz (telefon onayı için)").fill(YENI_SIFRE);
    await page.getByRole("button", { name: "Telefonu kaydet" }).click();
    await expect(page.getByRole("status")).toContainText("Telefon bilginiz kaydedildi");

    // Eski telefonla girilemez, yenisiyle girilir
    await page.getByRole("button", { name: "Çıkış" }).click();
    await arayuzdenGiris(page, bosluklu, YENI_SIFRE, "yonetici");
    await expect(page.getByRole("alert")).toBeVisible();
    await arayuzdenGiris(page, telefonBosluklu(`+90${yeniOn}`), YENI_SIFRE, "yonetici");
    await expect(page.getByRole("heading", { name: "Genel bakış", level: 1 })).toBeVisible();
  });

  test("yönetici, antrenörün telefonunu (girişini) değiştirir", async ({ page }) => {
    const belirtec = await yoneticiApiGirisi(page);
    const k = benzersiz();
    const giris = yeniAntrenorGirisi();
    const yeniGiris = yeniAntrenorGirisi();
    const yanit = await page.request.post("/api/antrenorler", {
      headers: { Authorization: `Bearer ${belirtec}` },
      data: { ad_soyad: `Antrenor ${k}`, telefon: giris },
    });
    expect(yanit.status()).toBe(201);
    const gecici = ((await yanit.json()) as { gecici_sifre: string }).gecici_sifre;

    await page.goto("/antrenorler");
    await page.getByRole("row", { name: new RegExp(`Antrenor ${k}`) }).getByRole("button", { name: "Düzenle" }).click();
    const modal = page.getByRole("dialog", { name: "Antrenörü düzenle" });
    await modal.getByLabel("Telefon").fill(yeniGiris);
    await expect(modal).toContainText("açık oturumları kapanır");
    await modal.getByRole("button", { name: "Kaydet" }).click();
    await expect(page.getByRole("row", { name: new RegExp(`Antrenor ${k}.*${telefonGorunen(yeniGiris).replace(/[.+]/g, "\\$&")}`) })).toBeVisible();

    await page.getByRole("button", { name: "Çıkış" }).click();
    await arayuzdenGiris(page, yeniGiris, gecici, "antrenor");
    await zorunluSifreyiBelirle(page, gecici);
    await expect(page).toHaveURL(/\/bugun$/);
  });
});
