import { arayuzdenGiris, expect, test, yoklamaOrtamiKur, yoneticiApiGirisi } from "../yardimci";

const yerel = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

test.describe("Ek ders", () => {
  test("antrenör öğrenciye ücretsiz ek ders ekler; ders hakkı değişmez; yoklamada rozet ve not; kaldırır", async ({ page }) => {
    test.slow();
    const o = await yoklamaOrtamiKur(page);

    const token = await yoneticiApiGirisi(page);
    const yetki = { Authorization: `Bearer ${token}` };
    const liste = await page.request.get("/api/antrenorler", { headers: yetki });
    expect(liste.ok(), await liste.text()).toBeTruthy();
    const antrenor = ((await liste.json()) as { id: string; ad_soyad: string }[]).find((a) => a.ad_soyad === o.antrenor.adSoyad);
    expect(antrenor, "antrenör listede").toBeTruthy();

    // Antrenörün ikinci grubu: bugün (yoklaması açık), boş kontenjanlı.
    const bugun = new Date();
    const grupBAdi = `Ek B ${o.grupAdi.replace("Yoklama ", "")}`;
    const g = await page.request.post("/api/gruplar", {
      headers: yetki,
      data: { ad: grupBAdi, antrenor_id: antrenor!.id, kontenjan: 5, program: [{ gun: ((bugun.getDay() + 6) % 7) + 1, baslangic: "00:00", bitis: "23:59" }] },
    });
    expect(g.status(), await g.text()).toBe(201);
    const u = await page.request.post("/api/oturumlar/uret", { headers: yetki, data: { baslangic: yerel(bugun), bitis: yerel(bugun) } });
    expect(u.ok(), await u.text()).toBeTruthy();

    // Telafi hakkı olsun ki "değişmedi" iddiası anlamlı olsun.
    const d = await page.request.post(`/api/ogrenciler/${o.geldi.id}/ders-hakki/duzeltme`, {
      headers: yetki,
      data: { sayac: "telafi", miktar: 1, neden: "E2E ek ders öncesi hak" },
    });
    expect(d.ok(), await d.text()).toBeTruthy();
    const hakOku = async () => {
      const r = await page.request.get(`/api/ogrenciler/${o.geldi.id}/ders-hakki`, { headers: yetki });
      expect(r.ok(), await r.text()).toBeTruthy();
      const j = (await r.json()) as { normal: number; telafi: number; kullanilabilir_telafi: number; hareketler: unknown[] };
      return { normal: j.normal, telafi: j.telafi, kullanilabilir: j.kullanilabilir_telafi, hareket: j.hareketler.length };
    };
    const once = await hakOku();
    expect(once.telafi).toBe(1);

    // Antrenör: Öğrencilerim → öğrenci → Ek ders ekle.
    await page.context().clearCookies();
    await arayuzdenGiris(page, o.antrenor.giris, o.antrenor.sifre);
    await expect(page).toHaveURL(/\/bugun$/);
    await page.goto("/ogrencilerim");
    await page.getByRole("button", { name: new RegExp(`${o.geldi.ad} ${o.geldi.soyad}: `) }).click();
    const sheet = page.getByRole("dialog", { name: new RegExp(o.geldi.ad) });
    await sheet.getByRole("button", { name: "Ek ders ekle" }).click();
    const adaylar = page.getByRole("dialog", { name: "Ek ders ekle" });
    const aday = adaylar.getByRole("listitem").filter({ hasText: grupBAdi }).first();
    await expect(aday).toBeVisible();
    await aday.getByRole("button", { name: /^Seç/ }).click();

    // Plan listesinde "Ek ders" rozeti.
    const plan = sheet.getByRole("listitem").filter({ hasText: grupBAdi });
    await expect(plan).toBeVisible();
    await expect(plan).toContainText("Ek ders");
    await expect(plan.getByRole("button", { name: "Taşı" })).toBeVisible();

    // Ders hakkı değişmedi.
    expect(await hakOku()).toEqual(once);

    // Yoklama: satırda rozet ve ücretsiz notu.
    const antrenorToken = await (async () => {
      const l = await page.request.post("/api/auth/login", { data: { giris: o.antrenor.giris, sifre: o.antrenor.sifre } });
      expect(l.ok(), await l.text()).toBeTruthy();
      return ((await l.json()) as { access_token: string }).access_token;
    })();
    const t = await page.request.get(`/api/antrenor/ogrenciler/${o.geldi.id}/telafi`, { headers: { Authorization: `Bearer ${antrenorToken}` } });
    const oturumId = ((await t.json()) as { planlar: { oturum_id: string }[] }).planlar[0].oturum_id;
    await page.goto(`/oturum/${oturumId}`);
    const satir = page.getByRole("listitem", { name: `${o.geldi.ad} ${o.geldi.soyad}` });
    await expect(satir).toContainText("Ek ders");
    await satir.getByRole("button", { name: "Gelmedi", exact: true }).click();
    await satir.getByRole("button", { name: "İzinli", exact: true }).click();
    await expect(satir.getByText("Ek ders ücretsizdir, ders hakkını etkilemez")).toBeVisible();

    // Kaldır (onay penceresini test yardımcısı otomatik onaylar); hak yine aynı.
    await satir.getByRole("button", { name: /Ek dersi kaldır/ }).click();
    await expect(page.getByRole("listitem", { name: `${o.geldi.ad} ${o.geldi.soyad}` })).toHaveCount(0);
    expect(await hakOku()).toEqual(once);
  });
});
