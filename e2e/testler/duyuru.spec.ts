import {
  arayuzdenGiris, benzersiz, expect, ogrenciOlusturAPI, test, yoklamaOrtamiKur, yoneticiApiGirisi, YENI_SIFRE,
  YONETICI_GIRIS, YONETICI_SIFRE,
} from "../yardimci";

const yerel = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

test.describe("Duyurular", () => {
  test("yönetici yaklaşan dersi iptal eder, velilere bildirir ve duyuruyu listede görür", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const yetki = { Authorization: `Bearer ${token}` };
    const k = benzersiz();
    const yarin = new Date();
    yarin.setDate(yarin.getDate() + 1);
    const gun = ((yarin.getDay() + 6) % 7) + 1; // isoweekday

    // Yarın dersi olan grup, bir öğrenci ve push cihazı kayıtlı veli hesabı.
    const grupAdi = `Duyuru ${k}`;
    const g = await page.request.post("/api/gruplar", {
      headers: yetki,
      data: { ad: grupAdi, kontenjan: 10, program: [{ gun, baslangic: "10:00", bitis: "11:30" }] },
    });
    expect(g.status(), await g.text()).toBe(201);
    const grup = (await g.json()) as { id: string };
    const ogr = await ogrenciOlusturAPI(page, token, "Duyuru");
    const e = await page.request.post(`/api/gruplar/${grup.id}/ogrenciler`, { headers: yetki, data: { ogrenci_id: ogr.id } });
    expect(e.ok(), await e.text()).toBeTruthy();
    const u = await page.request.post("/api/oturumlar/uret", { headers: yetki, data: { baslangic: yerel(yarin), bitis: yerel(yarin) } });
    expect(u.ok(), await u.text()).toBeTruthy();
    const t = await page.request.get(`/api/takvim?baslangic=${yerel(yarin)}&bitis=${yerel(yarin)}`, { headers: yetki });
    const oturum = ((await t.json()) as { id: string; grup: { ad: string } }[]).find((o) => o.grup.ad === grupAdi);
    expect(oturum).toBeTruthy();

    const h = await page.request.post(`/api/ogrenciler/${ogr.id}/hesap`, { headers: yetki, data: {} });
    expect(h.status(), await h.text()).toBe(200);
    const gecici = ((await h.json()) as { gecici_sifre: string }).gecici_sifre;
    const l1 = await page.request.post("/api/auth/login", { data: { giris: ogr.telefon, sifre: gecici } });
    expect(l1.ok(), await l1.text()).toBeTruthy();
    const d = await page.request.post("/api/auth/sifre-degistir", {
      headers: { Authorization: `Bearer ${((await l1.json()) as { access_token: string }).access_token}` },
      data: { mevcut_sifre: gecici, yeni_sifre: YENI_SIFRE },
    });
    expect(d.status(), await d.text()).toBe(204);
    const l2 = await page.request.post("/api/auth/login", { data: { giris: ogr.telefon, sifre: YENI_SIFRE } });
    expect(l2.ok(), await l2.text()).toBeTruthy();
    const abonelik = await page.request.post("/api/benim/push/abonelik", {
      headers: { Authorization: `Bearer ${((await l2.json()) as { access_token: string }).access_token}` },
      data: { endpoint: `https://push.ornek.test/${k}`, keys: { p256dh: "p".repeat(20), auth: "a".repeat(10) }, cihaz: "E2E" },
    });
    expect(abonelik.status(), await abonelik.text()).toBe(204);

    await page.context().clearCookies();
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await expect(page).toHaveURL(/\/genel-bakis$/);

    // Dersi iptal et (onay penceresi testte otomatik onaylanır).
    await page.goto(`/oturum/${oturum!.id}`);
    await page.getByRole("button", { name: "Dersi iptal et" }).click();
    await expect(page.getByText("İptal edildi", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Dersi iptal et" })).toHaveCount(0);
    const teklif = page.getByTestId("bildirim-teklifi");
    await expect(teklif).toContainText("Velilere bildirilsin mi?");
    await teklif.getByRole("link", { name: "Velilere bildir" }).click();

    // Form: hedef ders ve "Ders iptali" şablonu hazır gelir.
    await expect(page).toHaveURL(/\/duyurular\/yeni\?oturum=/);
    await expect(page.getByRole("radio", { name: "Ders oturumu" })).toBeChecked();
    await expect(page.getByLabel("Hazır şablon")).toHaveValue("ders_iptali");
    await expect(page.getByLabel("Mesaj")).toHaveValue(new RegExp(`${grupAdi} grubunun .* dersi iptal edilmiştir`));
    await expect(page.getByLabel("WhatsApp")).toBeDisabled();
    // Numara bağlı değil: seçenek kapalı ve nedeni yazılı (CI'da kurulmadı, yerelde Evolution var ama bağlı değil).
    await expect(page.getByTestId("whatsapp-nedeni")).toContainText(/WhatsApp (kurulmadığı|bağlı olmadığı) için kapalı\./);
    await expect(page.getByTestId("onizleme")).toContainText("1 veli (1 öğrenci) · uygulama bildirimi alacak: 1 · bildirimi kapalı veya cihazı yok: 0");

    await page.getByRole("button", { name: "Duyuruyu gönder" }).click();
    await expect(page).toHaveURL(/\/duyurular\/[0-9a-f-]{36}$/);
    await expect(page.getByRole("heading", { name: "Ders iptali" })).toBeVisible();
    const alicilar = page.getByRole("list", { name: "Alıcılar" });
    await expect(alicilar).toContainText(`${ogr.ad} ${ogr.soyad}`);
    await expect(alicilar).toContainText("Uygulama");

    // Listede kanal istatistiği görünür (e2e'de VAPID yok: gönderim bekler).
    await page.getByRole("link", { name: "Duyurular" }).first().click();
    const kayit = page.getByRole("listitem").filter({ hasText: grupAdi });
    await expect(kayit).toContainText("Uygulama: 0/1 gönderildi");
    await expect(kayit).toContainText("WhatsApp: —");
  });

  test("menüde Duyurular, Bildirimler'den önce gelir; boş form gönderilemez", async ({ page }) => {
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    const menu = page.getByRole("link", { name: /^(Duyurular|Bildirimler)$/ });
    await expect(menu.first()).toBeVisible();
    const adlar = await menu.allInnerTexts();
    expect(adlar.map((a) => a.trim()).slice(0, 2)).toEqual(["Duyurular", "Bildirimler"]);
    await page.getByRole("link", { name: "Duyurular" }).first().click();
    await expect(page.getByRole("heading", { name: "Duyurular" })).toBeVisible();
    await page.getByRole("link", { name: "Yeni duyuru" }).click();
    await expect(page.getByRole("button", { name: "Duyuruyu gönder" })).toBeDisabled();
  });

  test("antrenör dersi iptal et düğmesini görmez", async ({ page }) => {
    test.slow();
    const o = await yoklamaOrtamiKur(page);
    await arayuzdenGiris(page, o.antrenor.giris, o.antrenor.sifre);
    await page.getByRole("link", { name: new RegExp(o.grupAdi) }).click();
    await expect(page.getByRole("heading", { name: o.grupAdi })).toBeVisible();
    await expect(page.getByRole("button", { name: "Dersi iptal et" })).toHaveCount(0);
  });
});
