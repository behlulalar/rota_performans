import {
  benzersiz,
  expect,
  gecersizTcUret,
  KUCUK_PNG,
  ogrenciOlusturAPI,
  tcMaskeli,
  tcUret,
  telefonUret10,
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
    }
    // "Telefon (isteğe bağlı)" öğrenci alanı da eşleşir; hepsi 10 hane alır (+90 kutuda sabit).
    for (let i = 0; i < (await telefonlar.count()); i++) {
      await telefonlar.nth(i).fill(telefonUret10());
    }

    await page.getByLabel(/KVKK aydınlatma metnini okudum/).check();
    await page.getByLabel(/Fotoğraf çekimi ve kullanımına izin/).check();
    await page.getByLabel(/WhatsApp ile bilgilendirme/).check();

    await page.locator('input[type="file"]').setInputFiles({ name: "foto.png", mimeType: "image/png", buffer: KUCUK_PNG });
    // Seçilen fotoğraf önce kırpma penceresinde ayarlanır.
    const kirpma = page.getByRole("dialog", { name: "Fotoğrafı ayarla" });
    await expect(kirpma).toBeVisible();
    await kirpma.getByRole("slider", { name: "Yakınlaştırma" }).fill("2");
    await kirpma.getByRole("button", { name: "Kaydet" }).click();
    await expect(kirpma).toBeHidden();
    await expect(page.getByAltText("Seçilen fotoğraf önizlemesi")).toBeVisible();

    await page.getByRole("button", { name: "Kaydet" }).click();

    // Detay sayfası
    await expect(page).toHaveURL(/\/ogrenciler\/[0-9a-f-]{36}$/);
    await expect(page.getByRole("heading", { name: `${ad} ${soyad}` })).toBeVisible();
    // Fotoğraf yüklendiği için "Değiştir" düğmesi görünür; yükleme uyarısı yok.
    await expect(page.getByRole("button", { name: "Değiştir" })).toBeVisible();
    await expect(page.getByRole("status")).toHaveCount(0);

    // Kayıtlı fotoğraf "Ayarla" ile yeniden kaydırılıp kırpılabilir.
    await page.getByRole("button", { name: "Ayarla" }).click();
    const ayar = page.getByRole("dialog", { name: "Fotoğrafı ayarla" });
    await expect(ayar).toBeVisible();
    const alan = ayar.getByRole("group", { name: /Fotoğraf kırpma alanı/ });
    await ayar.getByRole("slider", { name: "Yakınlaştırma" }).fill("3");
    await alan.focus();
    await page.keyboard.press("ArrowLeft");
    await ayar.getByRole("button", { name: "Kaydet" }).click();
    await expect(ayar).toBeHidden();
    await expect(page.getByRole("button", { name: "Değiştir" })).toBeVisible();
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
    }
    // "Telefon (isteğe bağlı)" öğrenci alanı da eşleşir; hepsi 10 hane alır (+90 kutuda sabit).
    for (let i = 0; i < (await telefonlar.count()); i++) {
      await telefonlar.nth(i).fill(telefonUret10());
    }
    await page.getByLabel(/KVKK aydınlatma metnini okudum/).check();
    await page.getByRole("button", { name: "Kaydet" }).click();

    await expect(page.getByText("Geçerli bir T.C. kimlik numarası girin")).toBeVisible();
    await expect(page).toHaveURL(/\/ogrenciler\/yeni$/);

    const yanit = await page.request.get(`/api/ogrenciler?q=${ad}`, { headers: { Authorization: `Bearer ${token}` } });
    expect(((await yanit.json()) as { toplam: number }).toplam).toBe(0);
  });

  test("reşit öğrenci telefonsuz kaydedilemez; telefon kutusu en çok 10 hane tutar", async ({ page }) => {
    await yoneticiApiGirisi(page);
    const k = benzersiz();
    await page.goto("/ogrenciler/yeni");
    await page.getByLabel("Ad", { exact: true }).fill(`Resit${k}`);
    await page.getByLabel("Soyad", { exact: true }).fill(`Tel${k}`);
    await page.getByLabel("Doğum tarihi").fill("2000-01-01");

    await page.getByRole("button", { name: "Kaydet" }).click();
    await expect(page.getByText("Reşit öğrenci için telefon gerekli")).toBeVisible();
    await expect(page).toHaveURL(/\/ogrenciler\/yeni$/);

    const telefon = page.getByLabel("Telefon").first();
    await telefon.fill("532123456789");
    await expect(telefon).toHaveValue("5321234567");
    await telefon.fill("");
    await telefon.pressSequentially("90 532 123 45 67 89");
    await expect(telefon).toHaveValue("9053212345");
  });

  test("reşit geçişinde telefon kayıttan gelir; farklı numara girilirse kişisel bilgilerdeki telefon da değişir", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const k = benzersiz();
    const kayitli = "+90" + telefonUret10();
    const yeni10 = telefonUret10();
    const yanit = await page.request.post("/api/ogrenciler", {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        ad: `Resit${k}`,
        soyad: `Gecis${k}`,
        dogum_tarihi: "2015-01-01",
        kimlik_tur: "tc",
        kimlik_no: tcUret(),
        telefon: kayitli,
        iletisim_kisileri: [{ rol: "diger", ad_soyad: `Veli ${k}`, telefon: "+90" + telefonUret10(), birincil: true }],
        rizalar: { aydinlatma: true, foto: false, whatsapp: false },
      },
    });
    expect(yanit.status(), await yanit.text()).toBe(201);
    const { id } = (await yanit.json()) as { id: string };
    // Çocuk 18'e girmiş gibi: birincil kişi veli kalır, reşit uyarısı çıkar.
    const guncel = await page.request.patch(`/api/ogrenciler/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { dogum_tarihi: "2000-01-01" },
    });
    expect(guncel.status(), await guncel.text()).toBe(200);

    await page.goto(`/ogrenciler/${id}`);
    await page.getByRole("button", { name: "Reşit geçişi yap" }).click();
    const pencere = page.getByRole("dialog", { name: "Reşit geçişi" });
    const kutu = pencere.getByLabel("Öğrencinin telefonu");
    await expect(kutu).toHaveValue(kayitli.slice(3));

    await kutu.fill(yeni10);
    await pencere.getByRole("button", { name: "Geçişi yap" }).click();
    await expect(pencere).toBeHidden();

    const detay = (await (await page.request.get(`/api/ogrenciler/${id}`, { headers: { Authorization: `Bearer ${token}` } })).json()) as {
      telefon: string;
      birincil_iletisim: { telefon: string };
    };
    expect(detay.telefon).toBe("+90" + yeni10);
    expect(detay.birincil_iletisim.telefon).toBe("+90" + yeni10);
  });

  test("iletişim kişisinin yanında WhatsApp düğmesi var ve doğrudan sohbeti açar", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const ogr = await ogrenciOlusturAPI(page, token, "Whats");
    await page.goto(`/ogrenciler/${ogr.id}`);
    const kisiler = page.getByRole("list").filter({ has: page.getByText("Birincil") });
    const dugme = kisiler.getByRole("link", { name: /ile WhatsApp'ta yaz/ });
    await expect(dugme).toHaveCount(1);
    await expect(dugme).toHaveAttribute("href", `https://wa.me/${ogr.telefon.replace("+", "")}`);
    await expect(dugme).toHaveAttribute("target", "_blank");
    await expect(dugme).toHaveAttribute("rel", /noopener/);
  });
});
