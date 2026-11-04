import { arayuzdenGiris, expect, telefonUret10, test, yoklamaOrtamiKur } from "../yardimci";

test.describe("Antrenör: Bugün ve Profilim", () => {
  test("girişte Bugün açılır, bugünkü ders görünür ve yoklamaya gidilir", async ({ page }) => {
    test.slow();
    const o = await yoklamaOrtamiKur(page);

    await arayuzdenGiris(page, o.antrenor.giris, o.antrenor.sifre);
    await expect(page).toHaveURL(/\/bugun$/);
    await expect(page.getByRole("heading", { name: "Bugün", exact: true })).toBeVisible();

    // Özet kutucukları: 1 ders, 2 öğrenci.
    const ders = page.getByText("Ders", { exact: true }).locator("xpath=following-sibling::div");
    const ogrenci = page.getByText("Öğrenci", { exact: true }).locator("xpath=following-sibling::div");
    await expect(ders).toHaveText("1");
    await expect(ogrenci).toHaveText("2");

    // Sıradaki ders kartı: gün boyu açık olduğundan "Yoklamaya git" etkindir.
    const siradaki = page.getByRole("region", { name: "Sıradaki ders" });
    await expect(siradaki).toContainText(o.grupAdi);
    await expect(siradaki).toContainText("2 öğrenci");

    // Liste satırı: Bekliyor rozeti.
    const satir = page.getByRole("link", { name: new RegExp(`${o.grupAdi}.*Bekliyor`) });
    await expect(satir).toBeVisible();

    await siradaki.getByRole("link", { name: "Yoklamaya git" }).click();
    await expect(page).toHaveURL(/\/oturum\/[0-9a-f-]{36}$/);
    await expect(page.getByRole("heading", { name: o.grupAdi })).toBeVisible();
    await page.getByRole("button", { name: "Tümü geldi" }).click();
    await page.getByRole("button", { name: "Yoklamayı kaydet (2/2 işaretli)" }).click();
    await expect(page.getByText("Yoklama alındı")).toBeVisible();

    // Bugün'e dönünce ders "Alındı" görünür; sıradaki ders kartı kalmaz.
    await page.getByRole("navigation", { name: "Ana menü" }).getByRole("link", { name: "Bugün" }).click();
    await expect(page.getByRole("link", { name: new RegExp(`${o.grupAdi}.*Alındı`) })).toBeVisible();
    await expect(page.getByRole("region", { name: "Sıradaki ders" })).toHaveCount(0);
  });

  test("profil: ad ve telefon güncellenir, yenilemede kalır; giriş değişmez", async ({ page }) => {
    test.slow();
    const o = await yoklamaOrtamiKur(page);
    await arayuzdenGiris(page, o.antrenor.giris, o.antrenor.sifre);
    await expect(page).toHaveURL(/\/bugun$/);

    await page.getByRole("navigation", { name: "Ana menü" }).getByRole("link", { name: "Profilim" }).click();
    await expect(page).toHaveURL(/\/profilim$/);
    await expect(page.getByRole("heading", { name: "Profilim" })).toBeVisible();
    await expect(page.getByLabel("Giriş bilgisi")).toHaveValue(o.antrenor.giris);
    await expect(page.getByLabel("Giriş bilgisi")).toHaveAttribute("readonly", "");

    const telefon = telefonUret10();
    await page.getByLabel("Ad soyad").fill("yeni hoca adı");
    await page.getByLabel("Telefon").fill(telefon);
    await page.getByRole("button", { name: "Bilgileri kaydet" }).click();
    await expect(page.getByText("Bilgileriniz kaydedildi.")).toBeVisible();
    await expect(page.getByLabel("Ad soyad")).toHaveValue("Yeni Hoca Adı");

    await page.reload();
    await expect(page.getByLabel("Ad soyad")).toHaveValue("Yeni Hoca Adı");
    await expect(page.getByLabel("Telefon")).toHaveValue(telefon);
    await expect(page.getByLabel("Giriş bilgisi")).toHaveValue(o.antrenor.giris);

    // Geçersiz telefon istemcide reddedilir.
    await page.getByLabel("Telefon").fill("123");
    await page.getByRole("button", { name: "Bilgileri kaydet" }).click();
    await expect(page.getByRole("alert")).toContainText("Geçerli bir telefon numarası girin");

    // Görünüm kartı ve şifre kartı da bu sayfadadır.
    await expect(page.getByRole("heading", { name: "Görünüm" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Şifreyi değiştir" })).toBeVisible();
  });
});
