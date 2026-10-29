import { expect, test } from "../yardimci";

test("PWA: manifest, simgeler, service worker ve çevrimdışı sayfa sunulur", async ({ request, page }) => {
  const yanit = await request.get("/manifest.webmanifest");
  expect(yanit.status()).toBe(200);
  const manifest = await yanit.json();
  expect(manifest.name).toBe("Rota Performans Akademi");
  expect(manifest.start_url).toBe("/");
  expect(manifest.display).toBe("standalone");
  expect(manifest.icons.length).toBeGreaterThanOrEqual(3);
  expect(manifest.icons.some((i: { purpose?: string }) => i.purpose === "maskable")).toBe(true);

  for (const simge of manifest.icons as { src: string }[]) {
    const r = await request.get(simge.src);
    expect(r.status(), simge.src).toBe(200);
    expect(r.headers()["content-type"]).toContain("image/");
  }
  const apple = await request.get("/apple-touch-icon.png");
  expect(apple.status()).toBe(200);
  expect(apple.headers()["content-type"]).toContain("image/");

  const sw = await request.get("/sw.js");
  expect(sw.status()).toBe(200);
  expect(await sw.text()).toContain("addEventListener");
  const offline = await request.get("/offline.html");
  expect(offline.status()).toBe(200);
  expect(await offline.text()).toContain("İnternet bağlantısı yok");

  await page.goto("/giris");
  await expect(page.locator('link[rel="manifest"]')).toHaveAttribute("href", "/manifest.webmanifest");
  await expect(page.locator('link[rel="apple-touch-icon"]')).toHaveCount(1);
});
