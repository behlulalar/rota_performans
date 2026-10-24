import { createContext, useContext, useEffect, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { aktifBolum, aktifOge, ogeAktifMi, type MenuBolumu, type MenuOgesi } from "../lib/menu";
import Simge, { Ok } from "./Simge";
import TemaDugmesi from "./TemaDugmesi";

const MENU_ANAHTARI = "rota-alt-menu";

type KabukDegeri = { bolumAdi: string; menuGizli: boolean; menuyuGoster: () => void };
const KabukBaglami = createContext<KabukDegeri>({ bolumAdi: "", menuGizli: false, menuyuGoster: () => {} });
export const useKabuk = () => useContext(KabukBaglami);

function menuTercihiOku(): boolean {
  try {
    return localStorage.getItem(MENU_ANAHTARI) !== "kapali";
  } catch {
    return true;
  }
}
function menuTercihiYaz(acik: boolean) {
  try {
    localStorage.setItem(MENU_ANAHTARI, acik ? "acik" : "kapali");
  } catch {
    /* depolama kapalıysa tercih bu oturumla sınırlı kalır */
  }
}

function basHarfler(giris: string | undefined): string {
  const temiz = (giris ?? "").replace(/[^\p{L}\p{N}]/gu, "");
  return (temiz.slice(0, 2) || "?").toLocaleUpperCase("tr-TR");
}

function PasifOge({ o }: { o: MenuOgesi }) {
  return (
    <div
      aria-disabled="true"
      className="flex items-center gap-2.5 rounded-[3px] px-2.5 min-h-11 md:min-h-9 text-[13px] text-metin-soluk opacity-80 cursor-not-allowed select-none"
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
              className={`flex items-center gap-2.5 rounded-[3px] px-2.5 min-h-11 md:min-h-9 text-[13px] transition-colors ${
                ogeAktifMi(o, yol)
                  ? "bg-yuzey-yuksek text-metin font-medium"
                  : "text-metin-orta hover:bg-yuzey-yuksek hover:text-metin"
              }`}
            >
              <Simge ad={o.simge} sinif={ogeAktifMi(o, yol) ? "text-altin-metin" : ""} />
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

export default function Kabuk({ menu, sekmeler }: { menu: MenuBolumu[]; sekmeler?: MenuOgesi[] }) {
  const { kullanici, cikisYap } = useAuth();
  const { pathname } = useLocation();
  const rotaBolumu = aktifBolum(menu, pathname) ?? menu[0];
  const [secili, setSecili] = useState(rotaBolumu.anahtar);
  const [menuAcik, setMenuAcik] = useState(menuTercihiOku);
  const [cekmece, setCekmece] = useState(false);

  // Rota değişince bölüm yeniden rotadan seçilir; çekmece kapanır.
  useEffect(() => {
    setSecili(rotaBolumu.anahtar);
    setCekmece(false);
  }, [rotaBolumu.anahtar, pathname]);

  useEffect(() => {
    if (!cekmece) return;
    const kapat = (e: KeyboardEvent) => e.key === "Escape" && setCekmece(false);
    window.addEventListener("keydown", kapat);
    return () => window.removeEventListener("keydown", kapat);
  }, [cekmece]);

  const gosterilen = menu.find((b) => b.anahtar === secili) ?? rotaBolumu;
  const sayfaAdi = aktifOge(menu, pathname)?.ad ?? "Rota Performans";

  const menuDegistir = (acik: boolean) => {
    setMenuAcik(acik);
    menuTercihiYaz(acik);
  };
  const bolumSec = (anahtar: string) => {
    setSecili(anahtar);
    if (!menuAcik) menuDegistir(true);
  };

  return (
    <KabukBaglami.Provider
      value={{ bolumAdi: rotaBolumu.ad, menuGizli: !menuAcik, menuyuGoster: () => menuDegistir(true) }}
    >
      <div className={`min-h-dvh md:flex ${sekmeler ? "sekmeli-kabuk" : ""}`}>
        {/* Masaüstü: bölüm şeridi */}
        <nav
          aria-label="Bölümler"
          className="hidden md:flex flex-col items-center w-16 shrink-0 sticky top-0 h-dvh bg-serit py-3 gap-1"
        >
          <div
            aria-hidden="true"
            className="size-9 mb-3 rounded-lg border border-serit-ikon-secili/50 grid place-items-center text-serit-ikon-secili text-xs font-semibold tracking-wider"
          >
            RP
          </div>
          {menu.map((b) => {
            const sec = b.anahtar === secili;
            return (
              <button
                key={b.anahtar}
                type="button"
                onClick={() => bolumSec(b.anahtar)}
                aria-label={b.ad}
                aria-pressed={sec}
                title={b.ad}
                className={`relative grid place-items-center size-11 rounded-lg transition-colors ${
                  sec
                    ? "bg-white/10 text-serit-ikon-secili"
                    : "text-serit-ikon hover:text-serit-ikon-secili hover:bg-white/5"
                }`}
              >
                {sec && <span aria-hidden="true" className="absolute -left-2.5 top-2.5 bottom-2.5 w-[3px] rounded-r bg-serit-ikon-secili" />}
                <Simge ad={b.simge} />
              </button>
            );
          })}
          <div className="mt-auto flex flex-col items-center gap-1">
            <TemaDugmesi gorunum="serit" />
            <div
              title={kullanici?.giris}
              className="size-9 rounded-full border border-serit-ikon/40 grid place-items-center text-serit-ikon-secili text-[11px] font-semibold"
            >
              {basHarfler(kullanici?.giris)}
            </div>
            <button
              type="button"
              onClick={() => void cikisYap()}
              aria-label="Çıkış"
              title="Çıkış"
              className="grid place-items-center size-11 rounded-lg text-serit-ikon hover:text-serit-ikon-secili transition-colors"
            >
              <Simge ad="cikis" />
            </button>
          </div>
        </nav>

        {/* Masaüstü: bölüm alt menüsü */}
        {menuAcik && (
          <aside
            aria-label={`${gosterilen.ad} menüsü`}
            className="hidden md:block w-[220px] shrink-0 sticky top-0 h-dvh bg-menu border-r border-cizgi overflow-y-auto"
          >
            <div className="flex items-start justify-between gap-2 px-4 pt-5 pb-4 border-b border-cizgi">
              <div className="min-w-0">
                <div className="font-display font-medium text-[19px] leading-6">Rota Performans</div>
                <div className="eyebrow mt-1.5">{gosterilen.ad}</div>
              </div>
              <button
                type="button"
                onClick={() => menuDegistir(false)}
                aria-label="Menüyü gizle"
                title="Menüyü gizle"
                className="grid place-items-center size-8 rounded-[3px] text-metin-soluk hover:text-metin hover:bg-yuzey-yuksek shrink-0"
              >
                <Ok yon="sol" />
              </button>
            </div>
            <div className="p-2">
              <OgeListesi ogeler={gosterilen.ogeler} yol={pathname} />
            </div>
          </aside>
        )}

        <div className="flex-1 min-w-0">
          {/* Mobil: üst çubuk */}
          <header className="md:hidden sticky top-0 z-30 h-14 flex items-center gap-2 pl-4 pr-2 bg-serit text-white">
            <div className="flex-1 min-w-0">
              <div className="text-[11px] leading-4 font-semibold uppercase tracking-[0.18em] text-serit-ikon-secili truncate">
                {rotaBolumu.ad}
              </div>
              <div className="font-display font-medium text-[19px] leading-6 truncate">{sayfaAdi}</div>
            </div>
            <TemaDugmesi gorunum="serit" />
            <button
              type="button"
              onClick={() => setCekmece((a) => !a)}
              aria-label="Menüyü aç/kapat"
              aria-expanded={cekmece}
              className="grid place-items-center size-11 rounded-[3px] text-serit-ikon-secili"
            >
              <Simge ad={cekmece ? "kapat" : "menu"} />
            </button>
          </header>

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
                      <div className="flex items-center gap-2 px-2.5 mb-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-metin-soluk">
                        <Simge ad={b.simge} boyut={14} />
                        {b.ad}
                      </div>
                      <OgeListesi ogeler={b.ogeler} yol={pathname} onGit={() => setCekmece(false)} />
                    </div>
                  ))}
                </div>
                <div className="p-3 border-t border-cizgi flex items-center gap-2">
                  <TemaDugmesi />
                  <span className="flex-1 min-w-0 truncate text-[13px] text-metin-soluk" title={kullanici?.giris}>
                    {kullanici?.giris}
                  </span>
                  <button
                    type="button"
                    onClick={() => void cikisYap()}
                    className="inline-flex items-center gap-2 rounded-[3px] border border-cizgi-guclu px-3 min-h-11 text-[13px] text-metin hover:border-altin"
                  >
                    <Simge ad="cikis" />
                    Çıkış
                  </button>
                </div>
              </div>
            </div>
          )}

          <main
            className={`px-4 md:px-8 pt-6 md:py-8 max-w-[1800px] ${
              sekmeler ? "pb-[calc(5.5rem+env(safe-area-inset-bottom))] md:pb-8" : "pb-8"
            }`}
          >
            <Outlet />
          </main>
        </div>

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
                      className={`flex flex-col items-center justify-center gap-1 min-h-14 px-1 text-[11px] leading-none ${
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
                  className={`w-full flex flex-col items-center justify-center gap-1 min-h-14 px-1 text-[11px] leading-none ${
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
    </KabukBaglami.Provider>
  );
}
