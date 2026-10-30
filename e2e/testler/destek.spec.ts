import {
  arayuzdenGiris, destekApiGirisi, destekArayuzdenGiris, destekDurumuKaydet, destekKurtarmaKodlariniKaydet, destekKurtarmaKodu, DESTEK_GIRIS, DESTEK_SIFRE, destekKoduAl,
  expect, ogrenciOlusturAPI, test, YONETICI_GIRIS, YONETICI_SIFRE, yoneticiApiGirisi,
} from "../yardimci";

// Bu dosya ilk çalışır (playwright.config.ts): destek hesabının 2FA kurulumunu ilk senaryo yapar.
test.describe.configure({ mode: "serial" });

test.describe("Teknik destek", () => {
  test("destek-giris: şifre, QR kurulumu, kurtarma kodları ve panele giriş", async ({ page }) => {
    await page.goto("/destek-giris");
    await expect(page.getByRole("heading", { name: "Teknik destek girişi" })).toBeVisible();
    await page.getByLabel("E-posta").fill(DESTEK_GIRIS);
    await page.getByLabel("Şifre", { exact: true }).fill("yanlis-sifre-123");
    await page.getByRole("button", { name: "Devam et" }).click();
    await expect(page.getByRole("alert")).toContainText("hatalı");

    await page.getByLabel("Şifre", { exact: true }).fill(DESTEK_SIFRE);
    await page.getByRole("button", { name: "Devam et" }).click();

    // Kurulum: QR kodu ve elle girilecek anahtar
    await expect(page.getByText("İki adımlı doğrulama kurulumu")).toBeVisible();
    await expect(page.getByTestId("qr-kodu").locator("svg")).toBeVisible();
    const anahtar = page.getByTestId("gizli-anahtar");
    await expect(anahtar).toBeVisible();
    const gizli = (await anahtar.innerText()).replace(/\s/g, "");
    expect(gizli).toMatch(/^[A-Z2-7]{16,}$/);

    // Yanlış kod reddedilir
    await page.getByLabel("Doğrulama kodu").fill("000000");
    await page.getByRole("button", { name: "Kurulumu tamamla" }).click();
    await expect(page.getByRole("alert")).toContainText("Doğrulama kodu hatalı");

    destekDurumuKaydet({ gizli, kurtarma: [], kullanilan: [] });
    await page.getByLabel("Doğrulama kodu").fill(await destekKoduAl(gizli));
    await page.getByRole("button", { name: "Kurulumu tamamla" }).click();

    // Kurtarma kodları bir kez gösterilir
    await expect(page.getByRole("heading", { name: "Kurtarma kodlarınız" })).toBeVisible();
    await expect(page.getByText(/yalnızca bir kez gösterilir/)).toBeVisible();
    const kodlar = page.getByTestId("kurtarma-kodlari").locator("li");
    await expect(kodlar).toHaveCount(8);
    const liste = (await kodlar.allInnerTexts()).map((k) => k.trim());
    for (const k of liste) expect(k).toMatch(/^[a-z0-9]{5}-[a-z0-9]{5}$/i);
    destekKurtarmaKodlariniKaydet(liste);
    await expect(page.getByRole("button", { name: "Kopyala" })).toBeVisible();
    const indirme = page.waitForEvent("download");
    await page.getByRole("button", { name: ".txt indir" }).click();
    expect((await indirme).suggestedFilename()).toBe("rota-kurtarma-kodlari.txt");

    await page.getByRole("button", { name: "Kaydettim, devam et" }).click();
    await expect(page).toHaveURL(/\/genel-bakis$/);
  });

  test("destek menüsü, çıkışta destek-giris'e dönüş, kod ve kurtarma kodu ile giriş", async ({ page }) => {
    // Doğrulama adımı: kurulumdaki anahtardan üretilen 6 haneli kod
    await destekArayuzdenGiris(page);
    const menu = page.getByRole("complementary", { name: "Menü" });
    await expect(menu.getByText("Teknik destek", { exact: true })).toBeVisible();
    for (const ad of ["Sistem durumu", "Hesaplar", "Bildirim kuyruğu", "Denetim kaydı"]) {
      await expect(menu.getByRole("link", { name: ad })).toBeVisible();
    }
    await expect(menu.getByRole("link", { name: "Denetim kaydı" })).toHaveCount(1);

    await page.getByRole("button", { name: "Çıkış" }).click();
    await expect(page).toHaveURL(/\/destek-giris$/);

    // Kurtarma kodu: bir kez geçer, ikinci kullanım reddedilir
    const kurtarma = destekKurtarmaKodu();
    for (const sonuc of ["gecer", "reddedilir"] as const) {
      await page.goto("/destek-giris");
      await page.getByLabel("E-posta").fill(DESTEK_GIRIS);
      await page.getByLabel("Şifre", { exact: true }).fill(DESTEK_SIFRE);
      await page.getByRole("button", { name: "Devam et" }).click();
      await page.getByRole("button", { name: "Kurtarma kodu kullan" }).click();
      await page.getByLabel("Kurtarma kodu").fill(kurtarma);
      await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
      if (sonuc === "gecer") {
        await expect(page).toHaveURL(/\/genel-bakis$/);
        await page.getByRole("button", { name: "Çıkış" }).click();
        await expect(page).toHaveURL(/\/destek-giris$/);
      } else {
        await expect(page.getByRole("alert")).toContainText("Doğrulama kodu hatalı");
      }
    }
  });

  test("sistem durumu yüklenir ve yenilenir", async ({ page }) => {
    await destekApiGirisi(page);
    await page.goto("/destek/sistem-durumu");
    await expect(page.getByRole("heading", { name: "Sistem durumu", level: 1 })).toBeVisible();
    const kartlar = page.getByTestId("durum-karti");
    await expect(kartlar).toHaveCount(3);
    await expect(kartlar.filter({ hasText: "Veritabanı" })).toHaveAttribute("data-durum", "iyi");
    await expect(kartlar.filter({ hasText: "Redis" })).toHaveAttribute("data-durum", "iyi");
    await expect(kartlar.filter({ hasText: "Bildirim işçisi" })).toBeVisible();
    await expect(page.getByTestId("kuyruk-sayilari")).toBeVisible();
    await expect(page.getByText("Web Push")).toBeVisible();
    await expect(page.getByText(/Son güncelleme/)).toBeVisible();
    const istek = page.waitForResponse((r) => r.url().includes("/api/destek/sistem-durumu"));
    await page.getByRole("button", { name: "Yenile" }).click();
    expect((await istek).ok()).toBeTruthy();
  });

  test("hesaplarda arama ve veli hesabının şifresini sıfırlama", async ({ page, browser, baseURL }) => {
    const yonetici = await yoneticiApiGirisi(page);
    const ogrenci = await ogrenciOlusturAPI(page, yonetici, "Destek");
    const hesap = await page.request.post(`/api/ogrenciler/${ogrenci.id}/hesap`, { headers: { Authorization: `Bearer ${yonetici}` }, data: {} });
    expect(hesap.status(), await hesap.text()).toBeLessThan(300);

    await page.context().clearCookies();
    await destekApiGirisi(page);
    await page.goto("/destek/hesaplar");
    await expect(page.getByRole("heading", { name: "Hesaplar", level: 1 })).toBeVisible();

    // Rol filtresi: destek kendi satırını "siz" rozetiyle görür
    await page.getByRole("combobox", { name: "Rol filtresi" }).selectOption("destek");
    const kendi = page.getByRole("row", { name: new RegExp(DESTEK_GIRIS) });
    await expect(kendi).toBeVisible();
    await expect(kendi.getByText("siz", { exact: true })).toBeVisible();
    await expect(kendi.getByText("2FA açık")).toBeVisible();
    await expect(kendi.getByRole("button", { name: "Şifre sıfırla" })).toBeDisabled();
    await page.getByRole("combobox", { name: "Rol filtresi" }).selectOption("");

    await page.getByRole("searchbox", { name: "Hesap ara" }).fill(ogrenci.telefon);
    const satir = page.getByRole("row").filter({ hasText: "Veli" });
    await expect(satir).toHaveCount(1);
    await expect(page.getByRole("row", { name: new RegExp(DESTEK_GIRIS) })).toHaveCount(0);

    await satir.getByRole("button", { name: "Şifre sıfırla" }).click(); // onay penceresi otomatik onaylanır
    const kutu = page.getByRole("dialog", { name: /için yeni geçici şifre/ });
    await expect(kutu).toBeVisible();
    const gecici = (await kutu.locator("code").innerText()).trim();
    expect(gecici.length).toBeGreaterThanOrEqual(8);
    await kutu.getByRole("button", { name: "Kapat" }).click();
    await expect(kutu).toHaveCount(0);

    // Oturumlar penceresi açılır
    await satir.getByRole("button", { name: "Oturumlar" }).click();
    const oturumlar = page.getByRole("dialog", { name: /oturumları/ });
    await expect(oturumlar).toBeVisible();
    await oturumlar.getByRole("button", { name: "Kapat", exact: true }).click();

    // Geçici şifre gerçekten çalışır: veli zorunlu şifre ekranına düşer
    // (Ayrı bağlam: destek oturumu bozulmasın.)
    const veliBaglami = await browser.newContext({ baseURL, locale: "tr-TR", timezoneId: "Europe/Istanbul" });
    const veliSayfasi = await veliBaglami.newPage();
    await arayuzdenGiris(veliSayfasi, ogrenci.telefon, gecici, "veli");
    await expect(veliSayfasi).toHaveURL(/\/sifre-degistir$/);
    await veliBaglami.close();
  });

  test("bildirim kuyruğu listelenir ve denetim kaydı yeni yolda açılır", async ({ page }) => {
    await destekApiGirisi(page);
    await page.goto("/destek/bildirimler");
    await expect(page.getByRole("heading", { name: "Bildirim kuyruğu", level: 1 })).toBeVisible();
    await expect(page.getByRole("button", { name: "Tüm hatalıları yeniden dene" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Seçilenleri yeniden dene" })).toBeDisabled();
    await page.getByRole("combobox", { name: "Durum filtresi" }).selectOption("hata");
    await expect(page.getByText("Bu filtrede bildirim yok.").or(page.getByTestId("kuyruk-satiri").first())).toBeVisible();

    await page.goto("/destek/denetim-kaydi");
    await expect(page.getByRole("heading", { name: "Denetim kaydı", level: 1 })).toBeVisible();
    await expect(page.getByTestId("denetim-satiri").first()).toBeVisible();
  });

  test("yönetici menüsünde denetim yok, destek rotaları yöneticiyi uzaklaştırır, destek hesabı yönetici girişinden girilemez", async ({ page }) => {
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await expect(page).toHaveURL(/\/genel-bakis$/);
    const menu = page.getByRole("complementary", { name: "Menü" });
    await expect(menu.getByRole("link", { name: "Denetim kaydı" })).toHaveCount(0);
    await expect(menu.getByText("Teknik destek")).toHaveCount(0);

    for (const yol of ["/destek/sistem-durumu", "/destek/hesaplar", "/destek/bildirimler", "/destek/denetim-kaydi", "/denetim-kaydi"]) {
      await page.goto(yol);
      await expect(page).toHaveURL(/\/genel-bakis$/);
    }
    // Sunucu da reddeder
    const token = await yoneticiApiGirisi(page);
    const y = await page.request.get("/api/destek/sistem-durumu", { headers: { Authorization: `Bearer ${token}` } });
    expect(y.status()).toBe(403);

    // Yöneticiler sayfasında destek satırı salt okunur
    await page.goto("/yoneticiler");
    const satir = page.getByRole("row", { name: new RegExp(DESTEK_GIRIS) });
    await expect(satir.getByText("Teknik destek", { exact: true })).toBeVisible();
    await expect(satir.getByRole("button")).toHaveCount(0);

    // Destek hesabı yönetici girişinden girilemez
    await page.context().clearCookies();
    await arayuzdenGiris(page, DESTEK_GIRIS, DESTEK_SIFRE, "yonetici");
    await expect(page.getByRole("alert")).toContainText("hatalı");
    await expect(page).toHaveURL(/\/yonetici-giris$/);
  });

  test("destek yöneticiler sayfasında destek satırını düzenleyemez", async ({ page }) => {
    await destekApiGirisi(page);
    await page.goto("/yoneticiler");
    const satir = page.getByRole("row", { name: new RegExp(DESTEK_GIRIS) });
    await expect(satir.getByText("Teknik destek", { exact: true })).toBeVisible();
    await expect(satir.getByRole("button")).toHaveCount(0);
  });
});
