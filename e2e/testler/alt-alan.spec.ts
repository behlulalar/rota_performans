import { expect, test, YONETICI_GIRIS, YONETICI_SIFRE } from "../yardimci";

const port = new URL(process.env.E2E_BASE_URL ?? "http://127.0.0.1:5175").port || "5175";
const adres = (panel: string, yol = "/") => `http://${panel}.localhost:${port}${yol}`;

async function girisYap(page: import("@playwright/test").Page, panel: string) {
  await page.goto(adres(panel, "/giris"));
  await page.getByLabel("Telefon numarası").fill(YONETICI_GIRIS);
  await page.getByLabel("Şifre", { exact: true }).fill(YONETICI_SIFRE);
  await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
}

test.describe("Panel alt alan adları", () => {
  for (const [panel, ad] of [["veli", "Rota Veli"], ["yonetim", "Rota Yönetim"], ["antrenor", "Rota Antrenör"], ["destek", "Rota Destek"]]) {
    test(`${panel} alanı kendi manifestini sunar (${ad})`, async ({ page }) => {
      // Node'un istek bağlamı *.localhost'u çözmez; manifesti tarayıcı üzerinden okuruz.
      const yanit = await page.goto(adres(panel, "/manifest.webmanifest"));
      expect(yanit?.ok()).toBeTruthy();
      expect(JSON.parse(await page.locator("body").innerText()).short_name).toBe(ad);
    });
  }

  test("yonetim alanında yönetici /giris ile girer ve genel bakışa iner", async ({ page }) => {
    await girisYap(page, "yonetim");
    await expect(page).toHaveURL(/\/genel-bakis$/);
    await expect(page.getByRole("heading", { name: "Genel bakış" })).toBeVisible();
  });

  test("veli alanında yönetici bilgileri reddedilir", async ({ page }) => {
    await girisYap(page, "veli");
    await expect(page.getByRole("alert")).toContainText("Giriş bilgileri hatalı");
    await expect(page).toHaveURL(/\/giris$/);
  });

  test("yonetim alanında /panel (veli sayfası) başka yere yönlenir", async ({ page }) => {
    await page.goto(adres("yonetim", "/panel"));
    await expect(page).not.toHaveURL(/\/panel/);
    await expect(page).toHaveURL(/\/giris$/);
    await expect(page.getByRole("heading", { name: "Veli / öğrenci girişi" })).toHaveCount(0);
  });

  test("yonetim alanındaki oturum veli alanıyla paylaşılmaz", async ({ page }) => {
    await girisYap(page, "yonetim");
    await expect(page).toHaveURL(/\/genel-bakis$/);
    await page.goto(adres("veli", "/panel"));
    await expect(page).toHaveURL(/\/giris$/);
    await expect(page.getByRole("heading", { name: "Veli / öğrenci girişi" })).toBeVisible();
  });

  test("yonetim alanında eski /yonetici-giris adresi /giris'e yönlenir", async ({ page }) => {
    await page.goto(adres("yonetim", "/yonetici-giris"));
    await expect(page).toHaveURL(/\/giris$/);
  });
});
