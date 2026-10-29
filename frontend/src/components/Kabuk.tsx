import { useEffect, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { aktifBolum, aktifOge, ogeAktifMi, type MenuBolumu, type MenuOgesi } from "../lib/menu";
import Logo from "./Logo";
import { BolumBaglami } from "./SayfaBasligi";
import Simge from "./Simge";
import TemaDugmesi from "./TemaDugmesi";

const MENU_ANAHTARI = "rota-menu-gizli";

function PasifOge({ o }: { o: MenuOgesi }) {
  return (
    <div
      aria-disabled="true"
      className="flex items-center gap-2.5 rounded-[10px] px-2.5 min-h-11 md:min-h-9 text-[14px] text-metin-soluk opacity-80 cursor-not-allowed select-none"
    >
      <Simge ad={o.simge} />
      <span className="flex-1">{o.ad}</span>
      <span className="rounded-full border border-cizgi-guclu px-2 text-[10px] leading-4 text-metin-soluk">Yakında</span>
    </div>
  );
}

function OgeListesi({ ogeler, yol, onGit }: { ogeler: MenuOgesi[]; yol: string; onGit?: () => void }) {
  return (
    <ul className="space-y-0.5">
      {ogeler.map((o) => (
        <li key={o.ad}>
          {o.yol ? (
            <Link
              to={o.yol}
              onClick={onGit}
              aria-current={ogeAktifMi(o, yol) ? "page" : undefined}
              className={`flex items-center gap-2.5 rounded-[10px] px-2.5 min-h-11 md:min-h-9 text-[14px] transition-colors ${
                ogeAktifMi(o, yol)
                  ? "bg-birincil text-birincil-metin font-semibold"
                  : "text-metin-orta hover:bg-yuzey-yuksek hover:text-metin"
              }`}
            >
              <Simge ad={o.simge} />
              {o.ad}
            </Link>
          ) : (
            <PasifOge o={o} />
          )}
        </li>
      ))}
    </ul>
  );
}

function BolumBasligi({ b }: { b: MenuBolumu }) {
  return <div className="px-2.5 mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-metin-soluk">{b.ad}</div>;
}

/**
 * Siyah marka çubuğu + içerik. `yan`: masaüstünde gruplu sol menü (yönetici).
 * `ust`: menü bağlantıları çubuğun içinde, sol menü yok (veli, antrenör).
 * Mobilde ikisi de üst çubuk, çekmece ve (verilirse) altta sabit sekmeler kullanır.
 */
export default function Kabuk({
  menu,
  sekmeler,
  yerlesim = "yan",
}: {
  menu: MenuBolumu[];
  sekmeler?: MenuOgesi[];
  yerlesim?: "yan" | "ust";
}) {
  const { kullanici, cikisYap } = useAuth();
  const { pathname } = useLocation();
  const rotaBolumu = aktifBolum(menu, pathname) ?? menu[0];
  const [cekmece, setCekmece] = useState(false);
  // Masaüstünde sol menü gizlenip açılabilir; tercih bu tarayıcıda hatırlanır.
  const [menuGizli, setMenuGizli] = useState(() => {
    try {
      return localStorage.getItem(MENU_ANAHTARI) === "1";
    } catch {
      return false;
    }
  });
  function menuyuDegistir() {
    setMenuGizli((g) => {
      try {
        localStorage.setItem(MENU_ANAHTARI, g ? "0" : "1");
      } catch {
        /* depolama kapalıysa tercih yalnız bu oturumda geçerli */
      }
      return !g;
    });
  }
  const tumOgeler = menu.flatMap((b) => b.ogeler);

  useEffect(() => setCekmece(false), [pathname]);

  useEffect(() => {
    if (!cekmece) return;
    const kapat = (e: KeyboardEvent) => e.key === "Escape" && setCekmece(false);
    window.addEventListener("keydown", kapat);
    return () => window.removeEventListener("keydown", kapat);
  }, [cekmece]);

  const sayfaAdi = aktifOge(menu, pathname)?.ad ?? "Rota Performans";

  return (
    <BolumBaglami.Provider value={rotaBolumu.ad}>
      <div className={`min-h-dvh flex flex-col ${sekmeler ? "sekmeli-kabuk" : ""}`}>
        {/* Siyah marka çubuğu */}
        <header className="sticky top-0 z-30 h-14 shrink-0 flex items-center gap-3 px-4 md:px-6 bg-serit text-white">
          {yerlesim === "yan" && (
            <button
              type="button"
              onClick={menuyuDegistir}
              aria-label={menuGizli ? "Menüyü göster" : "Menüyü gizle"}
              aria-expanded={!menuGizli}
              aria-controls="yan-menu"
              className="hidden md:grid place-items-center size-10 -ml-2 rounded-[10px] text-serit-ikon hover:text-altin transition-colors"
            >
              <Simge ad="menu" />
            </button>
          )}
          <Logo />
          <span className="hidden md:block font-display text-[17px] leading-none mr-2">Rota Performans</span>
          <span className="md:hidden flex-1 min-w-0 font-display text-[18px] leading-none truncate">{sayfaAdi}</span>

          {yerlesim === "ust" && (
            <nav aria-label="Ana menü" className="hidden md:flex items-center gap-1 ml-2">
              {tumOgeler.map((o) =>
                o.yol ? (
                  <Link
                    key={o.ad}
                    to={o.yol}
                    aria-current={ogeAktifMi(o, pathname) ? "page" : undefined}
                    className={`px-3 min-h-9 inline-flex items-center rounded-[10px] text-[14px] transition-colors ${
                      ogeAktifMi(o, pathname) ? "text-altin font-semibold" : "text-serit-ikon hover:text-white"
                    }`}
                  >
                    {o.ad}
                  </Link>
                ) : null,
              )}
            </nav>
          )}

          <div className="hidden md:flex items-center gap-3 ml-auto">
            <TemaDugmesi gorunum="serit" />
            <span className="max-w-[16rem] truncate text-[13px] text-serit-ikon" title={kullanici?.giris}>
              {kullanici?.ad_soyad || kullanici?.giris}
            </span>
            <button
              type="button"
              onClick={() => void cikisYap()}
              aria-label="Çıkış"
              className="inline-flex items-center gap-2 rounded-[10px] border border-serit-ikon/40 px-3 min-h-9 text-[13px] text-white hover:border-altin hover:text-altin transition-colors"
            >
              <Simge ad="cikis" boyut={16} />
              Çıkış
            </button>
          </div>

          <div className="md:hidden flex items-center">
            <TemaDugmesi gorunum="serit" />
            <button
              type="button"
              onClick={() => setCekmece((a) => !a)}
              aria-label="Menüyü aç/kapat"
              aria-expanded={cekmece}
              className="grid place-items-center size-11 rounded-[10px] text-altin"
            >
              <Simge ad={cekmece ? "kapat" : "menu"} />
            </button>
          </div>
        </header>

        <div className="flex flex-1 min-w-0">
          {yerlesim === "yan" && !menuGizli && (
            <aside
              id="yan-menu"
              aria-label="Menü"
              className="hidden md:block w-[232px] shrink-0 sticky top-14 h-[calc(100dvh-3.5rem)] overflow-y-auto bg-menu border-r border-cizgi p-3 space-y-5"
            >
              {menu.map((b) => (
                <div key={b.anahtar}>
                  <BolumBasligi b={b} />
                  <OgeListesi ogeler={b.ogeler} yol={pathname} />
                </div>
              ))}
            </aside>
          )}

          <main
            className={`flex-1 min-w-0 px-4 md:px-8 pt-6 md:py-8 ${yerlesim === "ust" ? "max-w-6xl mx-auto w-full" : "max-w-[1800px]"} ${
              sekmeler ? "pb-[calc(5.5rem+env(safe-area-inset-bottom))] md:pb-8" : "pb-8"
            }`}
          >
            <Outlet />
          </main>
        </div>

        {/* Mobil çekmece */}
        {cekmece && (
          <div className={`md:hidden fixed inset-x-0 top-14 z-20 ${sekmeler ? "bottom-[calc(3.5rem+env(safe-area-inset-bottom))]" : "bottom-0"}`}>
            <button
              type="button"
              tabIndex={-1}
              aria-hidden="true"
              onClick={() => setCekmece(false)}
              className="absolute inset-0 bg-black/60"
            />
            <div
              role="dialog"
              aria-label="Menü"
              className="absolute inset-y-0 right-0 w-[min(20rem,88vw)] bg-menu border-l border-cizgi overflow-y-auto flex flex-col"
            >
              <div className="p-3 space-y-4 flex-1">
                {menu.map((b) => (
                  <div key={b.anahtar}>
                    <BolumBasligi b={b} />
                    <OgeListesi ogeler={b.ogeler} yol={pathname} onGit={() => setCekmece(false)} />
                  </div>
                ))}
              </div>
              <div className="p-3 border-t border-cizgi flex items-center gap-2">
                <span className="flex-1 min-w-0 truncate text-[13px] text-metin-soluk" title={kullanici?.giris}>
                  {kullanici?.ad_soyad || kullanici?.giris}
                </span>
                <button
                  type="button"
                  onClick={() => void cikisYap()}
                  className="inline-flex items-center gap-2 rounded-[10px] border border-cizgi-guclu px-3 min-h-11 text-[13px] text-metin hover:border-altin"
                >
                  <Simge ad="cikis" />
                  Çıkış
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Mobil: altta sabit hızlı sekme çubuğu */}
        {sekmeler && (
          <nav
            aria-label="Hızlı sekmeler"
            className="md:hidden fixed inset-x-0 bottom-0 z-40 bg-menu border-t border-cizgi pb-[env(safe-area-inset-bottom)]"
          >
            <ul className="flex">
              {sekmeler.map((o) => {
                const sec = ogeAktifMi(o, pathname);
                return (
                  <li key={o.ad} className="flex-1 min-w-0">
                    <Link
                      to={o.yol ?? "#"}
                      aria-current={sec ? "page" : undefined}
                      className={`flex flex-col items-center justify-center gap-1 min-h-14 px-1 text-[12px] leading-none ${
                        sec ? "text-altin-metin font-semibold" : "text-metin-soluk"
                      }`}
                    >
                      <Simge ad={o.simge} />
                      <span className="truncate max-w-full">{o.ad}</span>
                    </Link>
                  </li>
                );
              })}
              <li className="flex-1 min-w-0">
                <button
                  type="button"
                  onClick={() => setCekmece((a) => !a)}
                  aria-expanded={cekmece}
                  className={`w-full flex flex-col items-center justify-center gap-1 min-h-14 px-1 text-[12px] leading-none ${
                    cekmece ? "text-altin-metin font-semibold" : "text-metin-soluk"
                  }`}
                >
                  <Simge ad="menu" />
                  <span>Menü</span>
                </button>
              </li>
            </ul>
          </nav>
        )}
      </div>
    </BolumBaglami.Provider>
  );
}
