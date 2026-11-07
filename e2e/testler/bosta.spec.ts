import { arayuzdenGiris, expect, test, YONETICI_GIRIS, YONETICI_SIFRE } from "../yardimci";

// Saat sahte olduğu için 30 dakikalık bekleme anında geçer; sunucu gerçek saatle çalışır.
test.describe("Boşta kalınca otomatik çıkış", () => {
  test("30 dakika hareket yoksa sekme açık olsa bile oturum kapanır, uyarı gösterilir ve oturum sunucuda da biter", async ({ page }) => {
    await page.clock.install();
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await expect(page).toHaveURL(/\/genel-bakis$/);

    await page.clock.fastForward("29:00");
    await expect(page).toHaveURL(/\/genel-bakis$/);

    await page.clock.fastForward("02:00");
    await expect(page).toHaveURL(/\/yonetici-giris$/);
    await expect(page.getByRole("status").filter({ hasText: "30 dakika işlem yapılmadığından" })).toBeVisible();

    // Adres çubuğuna yazıp yeniden girmek de oturumu geri getirmez.
    const yenileme = await page.request.post("/api/auth/refresh");
    expect(yenileme.status()).toBe(401);
    await page.goto("/genel-bakis");
    await expect(page).toHaveURL(/\/yonetici-giris$/);
  });

  test("hareket süreyi yeniden başlatır: 20 dk + hareket + 20 dk açık kalır, ardından 31 dk hareketsizlik kapatır", async ({ page }) => {
    await page.clock.install();
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await expect(page).toHaveURL(/\/genel-bakis$/);

    await page.clock.fastForward("20:00");
    await page.mouse.move(200, 200);
    await page.mouse.move(260, 240);
    await page.clock.fastForward("20:00");
    await expect(page).toHaveURL(/\/genel-bakis$/);

    await page.clock.fastForward("11:00");
    await expect(page).toHaveURL(/\/yonetici-giris$/);
  });
});
