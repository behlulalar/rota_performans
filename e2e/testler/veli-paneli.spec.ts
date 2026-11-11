import {
  arayuzdenGiris, benzersiz, expect, odemeAlAPI, ogrenciOlusturAPI, paketAtaAPI, paketOlusturAPI, telefonBosluklu, test,
  yeniAntrenorGirisi, yoneticiApiGirisi, zorunluSifreyiBelirle,
} from "../yardimci";

async function veliHesabiAc(page: import("@playwright/test").Page, token: string, ogrenciId: string): Promise<string> {
  const yanit = await page.request.post(`/api/ogrenciler/${ogrenciId}/hesap`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {},
  });
  expect(yanit.status(), await yanit.text()).toBe(200);
  return ((await yanit.json()) as { gecici_sifre: string }).gecici_sifre;
}

test.describe("Veli paneli", () => {
  test("veli çocuğunun ders hakkını, paketini ve ödeme durumunu görür", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const ogr = await ogrenciOlusturAPI(page, token, "Panel");
    const paket = await paketOlusturAPI(page, token);
    const opId = await paketAtaAPI(page, token, ogr.id, paket.id);
    const gecici = await veliHesabiAc(page, token, ogr.id);

    await page.context().clearCookies();
    await arayuzdenGiris(page, telefonBosluklu(ogr.telefon), gecici);
    await zorunluSifreyiBelirle(page, gecici);

    // Tek çocuk: ana sayfa doğrudan çocuğun sayfasına yönlenir.
    await expect(page).toHaveURL(/\/panel\/cocuk\//);
    await expect(page.getByRole("heading", { name: `${ogr.ad} ${ogr.soyad}` })).toBeVisible();
    await expect(page.getByRole("status").filter({ hasText: "Ödemesi bekleyen paket var" })).toContainText(paket.ad);
    await expect(page.getByText("Planlanmış yaklaşan ders yok.")).toBeVisible();
    await page.getByRole("tab", { name: "Paket ve ödemeler" }).click();
    await expect(page).toHaveURL(/sekme=paket/);
    await expect(page.getByText("Ödeme bekliyor").first()).toBeVisible();

    // Ödeme alınınca ders hakkı yüklenir, uyarı kalkar.
    // Yönetici belirteci baştan alındı: yeniden giriş yapmak veli çerezini ezerdi.
    await odemeAlAPI(page, token, opId);
    await page.reload();
    await expect(page.getByRole("status").filter({ hasText: "Ödemesi bekleyen paket var" })).toHaveCount(0);
    // Dersler yüklendi, hakkı bitmiş değil.
    await expect(page.getByRole("status").filter({ hasText: "Ders hakkınız bitti" })).toHaveCount(0);
    await expect(page.getByRole("tab", { name: "Paket ve ödemeler" })).toHaveAttribute("aria-selected", "true"); // sekme yenilemede korunur
    await expect(page.getByText("Ödendi", { exact: true })).toBeVisible();
    await expect(page.getByText("Nakit")).toBeVisible();

    // Ödeme sonrası paketin dersleri "Ders hakkım" sekmesinde sayı sayı görünür.
    await page.getByRole("tab", { name: "Ders hakkım" }).click();
    const panel = page.getByRole("tabpanel");
    await expect(panel.getByText("Toplam ders")).toBeVisible();
    await expect(panel.getByText("Katıldığı")).toBeVisible();
    await expect(panel.getByText("Kalan", { exact: true }).first()).toBeVisible();
    await expect(panel.getByText("Telafi hakkım")).toBeVisible();
  });

  test("veli profilini günceller ve şifresini değiştirir", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const ogr = await ogrenciOlusturAPI(page, token, "Profil");
    const gecici = await veliHesabiAc(page, token, ogr.id);

    await page.context().clearCookies();
    await arayuzdenGiris(page, telefonBosluklu(ogr.telefon), gecici);
    await zorunluSifreyiBelirle(page, gecici);

    await page.getByRole("link", { name: "Profil" }).first().click();
    await expect(page).toHaveURL(/\/profil$/);
    await expect(page.getByRole("heading", { name: "Profil" })).toBeVisible();

    await page.getByLabel("Ad soyad").fill("Yeni Veli Adı");
    await page.getByRole("button", { name: "Bilgileri kaydet" }).click();
    await expect(page.getByText("Bilgileriniz kaydedildi.")).toBeVisible();
    await page.reload();
    await expect(page.getByLabel("Ad soyad")).toHaveValue("Yeni Veli Adı");

    // Zayıf şifre istemcide reddedilir.
    await page.getByLabel("Mevcut şifre").fill("yeni-sifre-12345");
    await page.getByLabel("Yeni şifre", { exact: true }).fill("kisa1");
    await page.getByLabel("Yeni şifre (tekrar)").fill("kisa1");
    await page.getByRole("button", { name: "Şifreyi değiştir" }).click();
    await expect(page.getByText("en az 10 karakter")).toBeVisible();

    await page.getByLabel("Yeni şifre", { exact: true }).fill("ikinci-guclu-sifre-1");
    await page.getByLabel("Yeni şifre (tekrar)").fill("ikinci-guclu-sifre-1");
    await page.getByRole("button", { name: "Şifreyi değiştir" }).click();
    await expect(page.getByText("Şifreniz değiştirildi.")).toBeVisible();

    await page.getByRole("button", { name: "Çıkış" }).click();
    await arayuzdenGiris(page, telefonBosluklu(ogr.telefon), "ikinci-guclu-sifre-1");
    await expect(page).toHaveURL(/\/panel\/cocuk\//);
  });

  test("veli bildirim tercihlerini kaydeder", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const ogr = await ogrenciOlusturAPI(page, token, "Tercih");
    const gecici = await veliHesabiAc(page, token, ogr.id);
    await page.context().clearCookies();
    await arayuzdenGiris(page, telefonBosluklu(ogr.telefon), gecici);
    await zorunluSifreyiBelirle(page, gecici);
    await page.getByRole("link", { name: "Profil" }).first().click();

    const devamsizlik = page.getByLabel("Devamsızlık bildirimi");
    await expect(devamsizlik).toBeChecked();
    await expect(page.getByText("kulübün iletişim izninizi kaydetmiş olması gerekir")).toBeVisible();
    await devamsizlik.uncheck();
    await page.getByLabel("Uygulama bildirimi (push)").uncheck();
    await page.getByRole("button", { name: "Tercihleri kaydet" }).click();
    await expect(page.getByText("Bildirim tercihleriniz kaydedildi.")).toBeVisible();

    await page.reload();
    await expect(page.getByLabel("Devamsızlık bildirimi")).not.toBeChecked();
    await expect(page.getByLabel("Uygulama bildirimi (push)")).not.toBeChecked();
    await expect(page.getByLabel("Ders hakkı hatırlatmaları")).toBeChecked();
    await expect(page.getByLabel("WhatsApp ile")).toBeChecked();

    // Cihaz bildirimi bölümü hatasız görünür (geliştirme sunucusunda service worker yok: izin istenmez).
    const cihaz = page.getByTestId("cihaz-bildirimi");
    await expect(cihaz.getByText("Bu cihaz", { exact: true })).toBeVisible();
    await expect(cihaz.getByText(/yalnızca yüklü|desteklemiyor|ana ekrana ekleyin|kapalı|açık/)).toBeVisible();
  });

  test("veli yönetici sayfalarına giremez", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const ogr = await ogrenciOlusturAPI(page, token, "Yetki");
    const gecici = await veliHesabiAc(page, token, ogr.id);
    await page.context().clearCookies();
    await arayuzdenGiris(page, telefonBosluklu(ogr.telefon), gecici);
    await zorunluSifreyiBelirle(page, gecici);
    await page.goto("/ogrenciler");
    await expect(page).toHaveURL(/\/panel\/cocuk\//);
  });
  test("veli Bize ulaşın sayfasında kulübü arar, yazar, haritada bulur; giriş sayfasında Instagram bağlantısı", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const kulup = await page.request.put("/api/ayarlar", {
      headers: { Authorization: `Bearer ${token}` },
      data: { telefon: "0532 123 45 67", eposta: "bilgi@rotaperformans.com", adres: "Atatürk Cad. No:1, Çankaya / Ankara", instagram: "@rotaperformans" },
    });
    expect(kulup.status(), await kulup.text()).toBe(200);
    const ogr = await ogrenciOlusturAPI(page, token, "Iletisim");
    const gecici = await veliHesabiAc(page, token, ogr.id);

    await page.context().clearCookies();
    // Veli giriş sayfasında Instagram bağlantısı (oturumsuz), yönetici girişinde yok.
    await page.goto("/yonetici-giris");
    await expect(page.getByRole("heading", { name: "Yönetici girişi" })).toBeVisible();
    await expect(page.getByText("Bizi Instagram'da takip edin")).toHaveCount(0);
    await page.goto("/giris");
    await expect(page.getByRole("link", { name: /Instagram'da takip edin/ })).toHaveAttribute("href", "https://www.instagram.com/rotaperformans/");
    const klasor = process.env.EKRAN_KLASORU;
    if (klasor) {
      for (const [ad, en, boy] of [["masaustu", 1280, 800], ["telefon", 390, 844]] as const) {
        await page.setViewportSize({ width: en, height: boy });
        for (const tema of ["light", "dark"] as const) {
          await page.evaluate((t) => localStorage.setItem("rota-tema-2", t), tema);
          await page.reload();
          await expect(page.getByText("@rotaperformans")).toBeVisible();
          await page.screenshot({ path: `${klasor}/giris-${ad}-${tema}.png` });
        }
      }
      await page.setViewportSize({ width: 1280, height: 800 });
    }
    await arayuzdenGiris(page, telefonBosluklu(ogr.telefon), gecici);
    await zorunluSifreyiBelirle(page, gecici);

    await page.getByRole("link", { name: "Bize ulaşın" }).first().click();
    await expect(page).toHaveURL(/\/iletisim$/);
    await expect(page.getByRole("heading", { name: "Bize ulaşın" })).toBeVisible();
    await expect(page.getByRole("link", { name: /Telefon/ })).toHaveAttribute("href", "tel:+905321234567");
    await expect(page.getByRole("link", { name: /WhatsApp/ })).toHaveAttribute("href", "https://wa.me/905321234567");
    await expect(page.getByRole("link", { name: /E-posta/ })).toHaveAttribute("href", "mailto:bilgi@rotaperformans.com");
    await expect(page.getByRole("link", { name: /Adres/ })).toHaveAttribute("href", /google\.com\/maps.*Ankara/);
    await expect(page.getByText("+90 532 123 45 67").first()).toBeVisible();
    await expect(page.getByRole("link", { name: /Instagram'da takip edin/ })).toHaveAttribute("href", "https://www.instagram.com/rotaperformans/");

    if (klasor) {
      for (const [ad, en, boy] of [["masaustu", 1280, 800], ["telefon", 390, 844]] as const) {
        await page.setViewportSize({ width: en, height: boy });
        for (const tema of ["light", "dark"] as const) {
          await page.evaluate((t) => localStorage.setItem("rota-tema-2", t), tema);
          await page.reload();
          await expect(page.getByRole("heading", { name: "Bize ulaşın" })).toBeVisible();
          await page.screenshot({ path: `${klasor}/iletisim-${ad}-${tema}.png` });
        }
      }
    }
  });
  test("yaklaşan dersler haftalara ayrılır, ilk iki hafta açık, gerisi düğmeyle açılır", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const yetki = { Authorization: `Bearer ${token}` };
    const k = benzersiz();
    const a = await page.request.post("/api/antrenorler", { headers: yetki, data: { ad_soyad: `Antrenor ${k}`, telefon: yeniAntrenorGirisi() } });
    expect(a.status(), await a.text()).toBe(201);
    const antrenorId = ((await a.json()) as { antrenor: { id: string } }).antrenor.id;
    const program = [1, 3, 5, 6].map((gun) => ({ gun, baslangic: "17:00", bitis: "18:00" }));
    const g = await page.request.post("/api/gruplar", { headers: yetki, data: { ad: `Yarış ${k}`, antrenor_id: antrenorId, kontenjan: 10, program } });
    expect(g.status(), await g.text()).toBe(201);
    const grupId = ((await g.json()) as { id: string }).id;
    const ogr = await ogrenciOlusturAPI(page, token, "Yaklasan");
    expect((await page.request.post(`/api/gruplar/${grupId}/ogrenciler`, { headers: yetki, data: { ogrenci_id: ogr.id } })).ok()).toBeTruthy();
    const gun = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    const bas = new Date();
    const bit = new Date(bas.getFullYear(), bas.getMonth(), bas.getDate() + 28);
    const u = await page.request.post("/api/oturumlar/uret", { headers: yetki, data: { baslangic: gun(bas), bitis: gun(bit) } });
    expect(u.ok(), await u.text()).toBeTruthy();
    const gecici = await veliHesabiAc(page, token, ogr.id);

    await page.context().clearCookies();
    await arayuzdenGiris(page, telefonBosluklu(ogr.telefon), gecici);
    await zorunluSifreyiBelirle(page, gecici);
    await expect(page).toHaveURL(/\/panel\/cocuk\//);

    const panel = page.getByRole("tabpanel");
    await expect(panel.getByRole("heading", { name: "Gelecek hafta" })).toBeVisible();
    const dugme = panel.getByRole("button", { name: /Sonraki haftaları göster \(\d+ ders\)/ });
    await expect(dugme).toBeVisible();
    const once = await panel.getByRole("listitem").count();
    expect(once).toBeLessThanOrEqual(8);
    const klasor = process.env.EKRAN_KLASORU;
    for (const [ad, en, boy] of [["masaustu", 1280, 900], ["telefon", 390, 844]] as const) {
      if (!klasor) break;
      await page.setViewportSize({ width: en, height: boy });
      for (const tema of ["light", "dark"] as const) {
        await page.evaluate((t) => localStorage.setItem("rota-tema-2", t), tema);
        await page.reload();
        await expect(dugme).toBeVisible();
        await page.screenshot({ path: `${klasor}/yaklasan-${ad}-${tema}.png`, fullPage: true });
      }
    }
    await dugme.click();
    expect(await panel.getByRole("listitem").count()).toBeGreaterThan(once);
    await expect(panel.getByRole("button", { name: "Daha az göster" })).toBeVisible();
  });
});
