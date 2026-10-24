import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";

export default function AntrenorYerlesim() {
  const { kullanici, cikisYap } = useAuth();
  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-20 bg-yuzey border-b border-cizgi">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center gap-3">
          <span className="text-sm font-medium truncate min-w-0">{kullanici?.giris}</span>
          <NavLink
            to="/takvim"
            className={({ isActive }) =>
              `ml-auto rounded-lg px-3 py-2 text-sm ${isActive ? "bg-yuzey-yuksek text-altin" : "text-metin-soluk hover:text-metin"}`
            }
          >
            Takvim
          </NavLink>
          <button
            onClick={() => void cikisYap()}
            className="rounded-lg border border-cizgi px-3 py-2 text-sm text-metin-soluk hover:border-altin hover:text-metin transition-colors"
          >
            Çıkış
          </button>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-4 py-4 sm:py-6">
        <Outlet />
      </main>
    </div>
  );
}
