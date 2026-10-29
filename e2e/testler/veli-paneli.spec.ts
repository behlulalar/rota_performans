import {
  arayuzdenGiris, expect, odemeAlAPI, ogrenciOlusturAPI, paketAtaAPI, paketOlusturAPI, telefonBosluklu, test,
  yoneticiApiGirisi, zorunluSifreyiBelirle,
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
    await expect(page.getByRole("tab", { name: "Paket ve ödemeler" })).toHaveAttribute("aria-selected", "true"); // sekme yenilemede korunur
    await expect(page.getByText("Ödendi", { exact: true })).toBeVisible();
    await expect(page.getByText("Nakit")).toBeVisible();
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
});
