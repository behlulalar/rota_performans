import {
  benzersiz,
  expect,
  gecersizTcUret,
  KUCUK_PNG,
  tcMaskeli,
  tcUret,
  telefonUret,
  test,
  yoneticiApiGirisi,
} from "../yardimci";

test.describe("Öğrenci kaydı", () => {
  test("form doldurulur, fotoğraf yüklenir, detayda kimlik maskeli görünür ve onayla açılır, listede aranır", async ({ page }) => {
    await yoneticiApiGirisi(page);
    const k = benzersiz();
    const ad = `Deneme${k}`;
    const soyad = `Yuzucu${k}`;
    const tc = tcUret();

    await page.goto("/ogrenciler/yeni");
    await page.getByLabel("Ad", { exact: true }).fill(ad);
    await page.getByLabel("Soyad", { exact: true }).fill(soyad);
    await page.getByLabel("Anne adı").fill("Anne Ornek");
    await page.getByLabel("Baba adı").fill("Baba Ornek");
    await page.getByLabel("Doğum tarihi").fill("2014-03-15");
    await page.getByLabel("Cinsiyet").selectOption("kadin");
    await page.getByLabel("T.C. kimlik numarası").fill(tc);

    // Varsayılan üç satır: anne (birincil), baba, diğer.
    const adlar = page.getByLabel("Ad soyad");
    const telefonlar = page.getByLabel("Telefon");
    for (const [i, kisi] of ["Anne", "Baba", "Diger"].entries()) {
      await adlar.nth(i).fill(`${kisi} ${k}`);
      await telefonlar.nth(i).fill(telefonUret());
    }

    await page.getByLabel(/KVKK aydınlatma metnini okudum/).check();
    await page.getByLabel(/Fotoğraf çekimi ve kullanımına izin/).check();
    await page.getByLabel(/WhatsApp ile bilgilendirme/).check();

    await page.locator('input[type="file"]').setInputFiles({ name: "foto.png", mimeType: "image/png", buffer: KUCUK_PNG });
    await expect(page.getByAltText("Seçilen fotoğraf önizlemesi")).toBeVisible();

    await page.getByRole("button", { name: "Kaydet" }).click();

    // Detay sayfası
    await expect(page).toHaveURL(/\/ogrenciler\/[0-9a-f-]{36}$/);
    await expect(page.getByRole("heading", { name: `${ad} ${soyad}` })).toBeVisible();
    // Fotoğraf yüklendiği için "Değiştir" düğmesi görünür; yükleme uyarısı yok.
    await expect(page.getByRole("button", { name: "Değiştir" })).toBeVisible();
    await expect(page.getByRole("status")).toHaveCount(0);
    await expect(page.getByText("Anne adı")).toBeVisible();

    // Maskeli kimlik; tam numara yok
    await expect(page.getByText(tcMaskeli(tc), { exact: true })).toBeVisible();
    await expect(page.getByText(tc, { exact: true })).toHaveCount(0);

    // Onay (window.confirm otomatik kabul) ile tam numara
    await page.getByRole("button", { name: "Tam numarayı göster" }).click();
    await expect(page.getByText(tc, { exact: true })).toBeVisible();

    // Listede aramayla bulunur
    await page.goto("/ogrenciler");
    await page.getByPlaceholder("Ad veya soyad ara…").fill(soyad);
    await expect(page.getByRole("link", { name: `${ad} ${soyad}` })).toBeVisible();
    await expect(page.getByRole("row", { name: new RegExp(soyad) })).toContainText(tcMaskeli(tc));
  });

  test("geçersiz T.C. numarası form hatası gösterir ve kayıt oluşmaz", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const k = benzersiz();
    const ad = `Gecersiz${k}`;

    await page.goto("/ogrenciler/yeni");
    await page.getByLabel("Ad", { exact: true }).fill(ad);
    await page.getByLabel("Soyad", { exact: true }).fill(`Tc${k}`);
    await page.getByLabel("Doğum tarihi").fill("2014-03-15");
    await page.getByLabel("T.C. kimlik numarası").fill(gecersizTcUret());
    const adlar = page.getByLabel("Ad soyad");
    const telefonlar = page.getByLabel("Telefon");
    for (const [i, kisi] of ["Anne", "Baba", "Diger"].entries()) {
      await adlar.nth(i).fill(`${kisi} ${k}`);
      await telefonlar.nth(i).fill(telefonUret());
    }
    await page.getByLabel(/KVKK aydınlatma metnini okudum/).check();
    await page.getByRole("button", { name: "Kaydet" }).click();

    await expect(page.getByText("Geçerli bir T.C. kimlik numarası girin")).toBeVisible();
    await expect(page).toHaveURL(/\/ogrenciler\/yeni$/);

    const yanit = await page.request.get(`/api/ogrenciler?q=${ad}`, { headers: { Authorization: `Bearer ${token}` } });
    expect(((await yanit.json()) as { toplam: number }).toplam).toBe(0);
  });
});
