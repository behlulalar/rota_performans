import { execFileSync } from "node:child_process";
import { arayuzdenGiris, expect, test, yoklamaOrtamiKur, YONETICI_GIRIS, YONETICI_SIFRE } from "../yardimci";

test.describe("Yoklama", () => {
  test("antrenör takvimden oturumu açar, yoklamayı alır; yönetici bakiyeyi düşmüş görür", async ({ page }) => {
    // Giriş hız sınırı beklemesi (20 sn) gerekebilir; süre üç katına çıkar.
    test.slow();
    const o = await yoklamaOrtamiKur(page);

    await arayuzdenGiris(page, o.antrenor.giris, o.antrenor.sifre);
    await expect(page).toHaveURL(/\/bugun$/);
    await expect(page.getByRole("link", { name: "Öğrenciler", exact: true })).toHaveCount(0);
    await page.getByRole("navigation", { name: "Ana menü" }).getByRole("link", { name: "Takvim" }).click();
    await expect(page).toHaveURL(/\/takvim$/);

    const kart = page.getByRole("link", { name: new RegExp(o.grupAdi) });
    await expect(kart).toBeVisible();
    await expect(kart).toContainText("2 öğrenci");
    await kart.click();

    await expect(page).toHaveURL(/\/oturum\/[0-9a-f-]{36}$/);
    await expect(page.getByRole("heading", { name: o.grupAdi })).toBeVisible();
    const satir = (ad: string) => page.getByRole("listitem", { name: new RegExp(ad) });
    await satir(o.geldi.ad).getByRole("button", { name: "Geldi", exact: true }).click();
    await satir(o.gelmedi.ad).getByRole("button", { name: "Gelmedi", exact: true }).click();
    await satir(o.gelmedi.ad).getByRole("button", { name: "Raporlu", exact: true }).click();
    await page.getByRole("button", { name: "Yoklamayı kaydet (2/2 işaretli)" }).click();

    const ozet = page.getByRole("dialog", { name: "Yoklama kaydedildi" });
    await expect(ozet).toBeVisible();
    await expect(ozet).toContainText("Geldi: 1");
    await expect(ozet).toContainText("Gelmedi: 1 (Raporlu: 1)");
    await expect(ozet).not.toContainText("işaretlenmedi");
    await expect(ozet).toContainText(/Yoklama \d{2}:\d{2}'e kadar düzeltilebilir\./);
    await expect(ozet.getByRole("button", { name: "Tamam" })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(ozet).toHaveCount(0);
    await expect(page.getByText("Yoklama alındı")).toBeVisible();
    await expect(satir(o.geldi.ad).getByRole("button", { name: "Geldi", exact: true })).toHaveAttribute("aria-pressed", "true");

    await page.getByRole("link", { name: "← Takvim" }).click();
    await expect(page.getByRole("link", { name: new RegExp(o.grupAdi) })).toContainText("Yoklama alındı");

    // Yönetici: paket yüklenmeden geldi olan öğrencinin kalan dersi 0 görünür, fazla işlenen ders kırmızı notla bildirilir.
    await page.getByRole("button", { name: "Çıkış" }).click();
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await expect(page).toHaveURL(/\/genel-bakis$/);
    await page.goto(`/ogrenciler/${o.geldi.id}`);
    await expect(page.getByText("Kalan ders").locator("xpath=following-sibling::div")).toHaveText("0");
    await expect(page.getByText("Ders hakkı bitti: paketle yüklenenden 1 ders fazla işlendi")).toBeVisible();
  });

  test("antrenör için yoklama 1 saat sonra kilitlenir; yönetici kilitli yoklamayı düzeltebilir", async ({ page }) => {
    test.slow();
    const o = await yoklamaOrtamiKur(page);
    await arayuzdenGiris(page, o.antrenor.giris, o.antrenor.sifre);
    await page.getByRole("navigation", { name: "Ana menü" }).getByRole("link", { name: "Takvim" }).click();
    await page.getByRole("link", { name: new RegExp(o.grupAdi) }).click();
    await expect(page).toHaveURL(/\/oturum\/[0-9a-f-]{36}$/);
    const oturumId = page.url().split("/").pop()!;
    const satir = (ad: string) => page.getByRole("listitem", { name: new RegExp(ad) });
    await expect(page.getByTestId("yoklama-duzenleme-saati")).toHaveCount(0);
    await satir(o.geldi.ad).getByRole("button", { name: "Geldi", exact: true }).click();
    await page.getByRole("button", { name: "Yoklamayı kaydet (1/2 işaretli)" }).click();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("yoklama-duzenleme-saati")).toContainText(/Düzenleme \d{2}:\d{2}'e kadar açık/);
    await expect(page.getByRole("button", { name: /Yoklamayı kaydet/ })).toBeVisible();

    // Süre doldu (yalnız ENV=e2e konteynerinde çalışan test komutu).
    execFileSync("docker", ["exec", "rota-e2e-backend", "python", "-m", "app.cli", "e2e-yoklama-kilidi-gecir", oturumId]);
    await page.reload();
    await expect(page.getByTestId("yoklama-kilitli")).toContainText("Yoklama kilitlendi · düzeltme için yöneticiye başvurun");
    await expect(page.getByTestId("yoklama-duzenleme-saati")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Yoklamayı kaydet/ })).toHaveCount(0);
    await expect(satir(o.geldi.ad).getByRole("button", { name: "Geldi", exact: true })).toBeDisabled();
    await expect(satir(o.gelmedi.ad).getByRole("button", { name: "Gelmedi", exact: true })).toBeDisabled();

    // Yönetici: düzenleyebilir, not görünür.
    await page.getByRole("button", { name: "Çıkış" }).click();
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await page.goto(`/oturum/${oturumId}`);
    await expect(page.getByTestId("yoklama-yonetici-notu")).toContainText("Kilit süresi doldu; yönetici olarak düzeltiyorsunuz");
    await satir(o.gelmedi.ad).getByRole("button", { name: "Geldi", exact: true }).click();
    await page.getByRole("button", { name: /Yoklamayı kaydet/ }).click();
    const ozet = page.getByRole("dialog", { name: "Yoklama kaydedildi" });
    await expect(ozet).toContainText("Yönetici olarak yoklamayı daha sonra da düzeltebilirsiniz.");
  });
});
