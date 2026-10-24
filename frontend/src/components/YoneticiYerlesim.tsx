import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";

const MENU = [
  { yol: "/genel-bakis", ad: "Genel bakış" },
  { yol: "/ogrenciler", ad: "Öğrenciler" },
];

export default function YoneticiYerlesim() {
  const { kullanici, cikisYap } = useAuth();
  const [acik, setAcik] = useState(false);

  const baglanti = ({ isActive }: { isActive: boolean }) =>
    `block rounded-lg px-3 py-2 text-sm transition-colors ${
      isActive ? "bg-yuzey-yuksek text-altin" : "text-metin-soluk hover:text-metin"
    }`;

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-20 bg-yuzey border-b border-cizgi">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center gap-4">
          <div className="text-altin text-xs tracking-[0.3em] uppercase">Rota Performans</div>
          <nav className="hidden md:flex gap-1 ml-4">
            {MENU.map((m) => (
              <NavLink key={m.yol} to={m.yol} className={baglanti}>
                {m.ad}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto hidden md:flex items-center gap-3 text-sm">
            <span className="text-metin-soluk">{kullanici?.giris}</span>
            <button
              onClick={() => void cikisYap()}
              className="rounded-lg border border-cizgi px-3 py-1.5 text-metin-soluk hover:border-altin hover:text-metin transition-colors"
            >
              Çıkış
            </button>
          </div>
          <button
            className="ml-auto md:hidden rounded-lg border border-cizgi px-3 py-1.5 text-sm"
            aria-expanded={acik}
            aria-label="Menüyü aç/kapat"
            onClick={() => setAcik((a) => !a)}
          >
            {acik ? "Kapat" : "Menü"}
          </button>
        </div>
        {acik && (
          <div className="md:hidden border-t border-cizgi px-4 py-3 space-y-1">
            {MENU.map((m) => (
              <NavLink key={m.yol} to={m.yol} className={baglanti} onClick={() => setAcik(false)}>
                {m.ad}
              </NavLink>
            ))}
            <div className="pt-3 mt-2 border-t border-cizgi flex items-center justify-between text-sm">
              <span className="text-metin-soluk">{kullanici?.giris}</span>
              <button
                onClick={() => void cikisYap()}
                className="rounded-lg border border-cizgi px-3 py-1.5 text-metin-soluk hover:border-altin"
              >
                Çıkış
              </button>
            </div>
          </div>
        )}
      </header>
      <main className="max-w-6xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
