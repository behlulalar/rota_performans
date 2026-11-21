import { arayuzdenGiris, expect, test, yoklamaOrtamiKur, yoneticiApiGirisi } from "../yardimci";

const yerel = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

test.describe("Antrenör telafi planlama", () => {
  test("antrenör Öğrencilerim'den telafi planlar ve kaldırır", async ({ page }) => {
    test.slow();
    const o = await yoklamaOrtamiKur(page);

    // Yönetici: öğrenciye elle 1 telafi hakkı, antrenöre ikinci bir grup ve yarının oturumu.
    const token = await yoneticiApiGirisi(page);
    const yetki = { Authorization: `Bearer ${token}` };
    const liste = await page.request.get("/api/antrenorler", { headers: yetki });
    expect(liste.ok(), await liste.text()).toBeTruthy();
    const antrenor = ((await liste.json()) as { id: string; ad_soyad: string }[]).find((a) => a.ad_soyad === o.antrenor.adSoyad);
    expect(antrenor, "antrenör listede").toBeTruthy();

    const bugun = new Date();
    const yarin = new Date(bugun.getFullYear(), bugun.getMonth(), bugun.getDate() + 1);
    const yarinGun = ((yarin.getDay() + 6) % 7) + 1;
    const grupBAdi = `Telafi B ${o.grupAdi.replace("Yoklama ", "")}`;
    const g = await page.request.post("/api/gruplar", {
      headers: yetki,
      data: { ad: grupBAdi, antrenor_id: antrenor!.id, kontenjan: 5, program: [{ gun: yarinGun, baslangic: "00:00", bitis: "23:59" }] },
    });
    expect(g.status(), await g.text()).toBe(201);
    const u = await page.request.post("/api/oturumlar/uret", { headers: yetki, data: { baslangic: yerel(bugun), bitis: yerel(yarin) } });
    expect(u.ok(), await u.text()).toBeTruthy();

    const d = await page.request.post(`/api/ogrenciler/${o.geldi.id}/ders-hakki/duzeltme`, {
      headers: yetki,
      data: { sayac: "telafi", miktar: 1, neden: "E2E antrenör telafi hakkı" },
    });
    expect(d.ok(), await d.text()).toBeTruthy();

    // Antrenör: Öğrencilerim'de rozet.
    await page.context().clearCookies();
    await arayuzdenGiris(page, o.antrenor.giris, o.antrenor.sifre);
    await expect(page).toHaveURL(/\/bugun$/);
    await page.goto("/ogrencilerim");
    const satir = page.getByRole("button", { name: new RegExp(`${o.geldi.ad} ${o.geldi.soyad}: telafi`) });
    await expect(satir).toContainText("Telafi 1");

    // Alt pencere: boş liste, planla.
    await satir.click();
    const sheet = page.getByRole("dialog", { name: new RegExp(o.geldi.ad) });
    await expect(sheet.getByText("Planlı telafi veya ek ders yok.")).toBeVisible();
    await expect(sheet.getByText(/Planlanabilir:\s*1/)).toBeVisible();
    await sheet.getByRole("button", { name: "Telafi planla" }).click();

    const aday = page.getByRole("dialog", { name: "Telafi planla" }).getByRole("listitem").filter({ hasText: grupBAdi }).first();
    await expect(aday).toBeVisible();
    await aday.getByRole("button", { name: /^Seç/ }).click();

    // Plan sheet'te Taşı / Kaldır ile görünür.
    const plan = sheet.getByRole("listitem").filter({ hasText: grupBAdi });
    await expect(plan).toBeVisible();
    await expect(plan.getByRole("button", { name: "Taşı" })).toBeVisible();
    await expect(sheet.getByText(/Planlanabilir:\s*0/)).toBeVisible();

    // Kaldır: onay penceresi çıkar (test yardımcısı otomatik onaylar), plan gider ve hak iade edilir.
    await plan.getByRole("button", { name: "Kaldır" }).click();
    await expect(sheet.getByText("Planlı telafi veya ek ders yok.")).toBeVisible();
    await expect(sheet.getByText(/Planlanabilir:\s*1/)).toBeVisible();
  });
});
