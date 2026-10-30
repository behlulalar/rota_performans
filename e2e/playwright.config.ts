import { defineConfig, devices } from "@playwright/test";

// Testler ayrı bir ortama (ENV=e2e, ayrı veritabanı) karşı çalışır; geliştirme verisine dokunmaz.
export default defineConfig({
  testDir: "./testler",
  // Giriş hız sınırı IP başına dakikada 20 olduğu için testler sırayla çalışır.
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"], ["html", { open: "never" }]],
  use: {
    // Tarayıcı da backend gibi İstanbul saatini kullansın (gün sınırlarında tutarlılık).
    timezoneId: "Europe/Istanbul",
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:5175",
    locale: "tr-TR",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    // Destek hesabının 2FA kurulumu yalnız bir kez yapılabilir (e2e-tohum sıfırlar): kurulum senaryosunu
    // içeren destek.spec.ts diğer dosyalardan önce çalışır.
    { name: "destek", use: { ...devices["Desktop Chrome"] }, testMatch: /destek\.spec\.ts/ },
    { name: "chromium", use: { ...devices["Desktop Chrome"] }, testIgnore: /(mobil|destek)\.spec\.ts/, dependencies: ["destek"] },
    // Mobil profil yalnızca mobil görünüm senaryosu için.
    { name: "mobil", use: { ...devices["Pixel 7"] }, testMatch: /mobil\.spec\.ts/ },
  ],
});
