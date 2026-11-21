import { arayuzdenGiris, benzersiz, expect, ogrenciOlusturAPI, test, yoneticiApiGirisi, YONETICI_GIRIS, YONETICI_SIFRE } from "../yardimci";

const yerel = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

test.describe("Telafi", () => {
  test("yönetici elle telafi hakkı ekler, ders planlar ve geri alır", async ({ page }) => {
    const token = await yoneticiApiGirisi(page);
    const yetki = { Authorization: `Bearer ${token}` };
    const k = benzersiz();
    const bugun = new Date();
    const gun = ((bugun.getDay() + 6) % 7) + 1;

    const grupKur = async (ad: string, program: { gun: number; baslangic: string; bitis: string }[], kontenjan: number) => {
      const g = await page.request.post("/api/gruplar", { headers: yetki, data: { ad, kontenjan, program } });
      expect(g.status(), await g.text()).toBe(201);
      return (await g.json()) as { id: string };
    };
    const grupA = await grupKur(`Telafi A ${k}`, [{ gun: (gun % 7) + 1, baslangic: "10:00", bitis: "11:00" }], 10);
    const grupBAdi = `Telafi B ${k}`;
    await grupKur(grupBAdi, [{ gun, baslangic: "00:00", bitis: "23:59" }], 5);

    const ogr = await ogrenciOlusturAPI(page, token, "Telafi");
    const e = await page.request.post(`/api/gruplar/${grupA.id}/ogrenciler`, { headers: yetki, data: { ogrenci_id: ogr.id } });
    expect(e.ok(), await e.text()).toBeTruthy();

    const u = await page.request.post("/api/oturumlar/uret", {
      headers: yetki,
      data: { baslangic: yerel(bugun), bitis: yerel(new Date(bugun.getFullYear(), bugun.getMonth(), bugun.getDate() + 1)) },
    });
    expect(u.ok(), await u.text()).toBeTruthy();

    await page.context().clearCookies();
    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await expect(page).toHaveURL(/\/genel-bakis$/);
    await page.goto(`/ogrenciler/${ogr.id}`);

    const deger = (etiket: string) => page.getByText(etiket, { exact: true }).locator("xpath=following-sibling::div");
    await expect(page.getByRole("button", { name: "Telafi planla" })).toBeDisabled();

    await page.getByRole("button", { name: "Elle düzeltme" }).click();
    const pencere = page.getByRole("dialog", { name: "Elle düzeltme" });
    await pencere.getByLabel("Sayaç").selectOption("telafi");
    await pencere.getByLabel("Miktar").fill("1");
    await pencere.getByLabel("Neden").fill("E2E telafi hakkı");
    await expect(pencere.getByText("Düzeltmeler silinemez, kayıt altına alınır.")).toBeVisible();
    await pencere.getByRole("button", { name: "Düzeltmeyi kaydet" }).click();
    await expect(pencere).toHaveCount(0);

    await expect(deger("Telafi")).toHaveText("1");
    await expect(deger("Kullanılabilir telafi")).toHaveText("1");

    await page.getByRole("button", { name: "Telafi planla" }).click();
    const planPenceresi = page.getByRole("dialog", { name: "Telafi planla" });
    const aday = planPenceresi.getByRole("listitem").filter({ hasText: grupBAdi }).first();
    await expect(aday).toContainText("boş yer");
    await aday.getByRole("button", { name: "Seç" }).click();
    await expect(planPenceresi).toHaveCount(0);

    const plan = page.getByRole("listitem").filter({ hasText: grupBAdi });
    await expect(plan).toContainText("Bekliyor");
    await expect(deger("Kullanılabilir telafi")).toHaveText("0");

    await page.getByRole("button", { name: /Hareket geçmişi/ }).click();
    const satir = page.getByRole("listitem").filter({ hasText: "Elle düzeltme" });
    await expect(satir).toContainText("E2E telafi hakkı");

    await plan.getByRole("button", { name: "Geri al" }).click();
    await expect(deger("Kullanılabilir telafi")).toHaveText("1");
    await expect(page.getByText("Planlanmış telafi veya ek ders yok.")).toBeVisible();
  });
});
