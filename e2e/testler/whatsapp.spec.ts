import { arayuzdenGiris, expect, test, YONETICI_GIRIS, YONETICI_SIFRE } from "../yardimci";

// Gerçek Evolution/WhatsApp'a gidilmez: /api/whatsapp yanıtları tarayıcıda taklit edilir.
const kareler = Array.from({ length: 21 * 21 }, (_, i) => ((i * 7919) % 3 === 0 || i % 21 < 7 && Math.floor(i / 21) < 7 ? `<rect x="${i % 21}" y="${Math.floor(i / 21)}" width="1" height="1"/>` : "")).join("");
const QR = `data:image/svg+xml;utf8,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 21 21" shape-rendering="crispEdges">${kareler}</svg>`)}`;

test.describe("WhatsApp bağlantısı", () => {
  test("yönetici QR oluşturur, okutulunca bağlı görünür, bağlantıyı keser", async ({ page }) => {
    let durum: "bagli_degil" | "baglaniyor" | "bagli" = "bagli_degil";
    let kesildi = false;
    const yanit = () => ({
      durum, qr: durum === "baglaniyor" ? QR : null,
      numara: durum === "bagli" ? "+905321234567" : null, profil_adi: durum === "bagli" ? "Rota Performans" : null,
    });
    await page.route("**/api/whatsapp", (r) => r.fulfill({ json: yanit() }));
    await page.route("**/api/whatsapp/baglan", (r) => {
      if (durum === "bagli_degil") durum = "baglaniyor";
      return r.fulfill({ json: yanit() });
    });
    await page.route("**/api/whatsapp/kes", (r) => {
      kesildi = true;
      durum = "bagli_degil";
      return r.fulfill({ json: yanit() });
    });

    await arayuzdenGiris(page, YONETICI_GIRIS, YONETICI_SIFRE);
    await page.goto("/ayarlar");
    const kart = page.locator("section").filter({ has: page.getByRole("heading", { name: "WhatsApp bağlantısı" }) });
    await expect(kart.getByText("Bağlı değil")).toBeVisible();
    const klasor = process.env.EKRAN_KLASORU;
    const cek = async (ad: string) => klasor && (await kart.screenshot({ path: `${klasor}/whatsapp-${ad}.png` }));
    await cek("bagli-degil");

    await kart.getByRole("button", { name: "QR kodu oluştur" }).click();
    await expect(kart.getByRole("img", { name: "WhatsApp bağlantı QR kodu" })).toBeVisible();
    await expect(kart.getByText("QR bekleniyor")).toBeVisible();
    await cek("qr");

    durum = "bagli"; // telefonda okutuldu; kart birkaç saniye içinde kendiliğinden güncellenir
    await expect(kart.getByText("+90 532 123 45 67")).toBeVisible({ timeout: 10000 });
    await expect(kart.getByText("Rota Performans")).toBeVisible();
    await cek("bagli");

    await kart.getByRole("button", { name: "Bağlantıyı kes" }).click();
    await expect(kart.getByRole("button", { name: "QR kodu oluştur" })).toBeVisible();
    expect(kesildi).toBe(true);
  });
});
