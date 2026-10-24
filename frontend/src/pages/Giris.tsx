import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { ApiHata } from "../lib/api";

export default function Giris() {
  const { kullanici, girisYap } = useAuth();
  const [giris, setGiris] = useState("");
  const [sifre, setSifre] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);

  if (kullanici) return <Navigate to="/" replace />;

  async function gonder(e: FormEvent) {
    e.preventDefault();
    setHata(null);
    setGonderiliyor(true);
    try {
      await girisYap(giris, sifre);
    } catch (err) {
      setHata(err instanceof ApiHata ? err.message : "Bağlantı kurulamadı. Lütfen tekrar deneyin.");
    } finally {
      setGonderiliyor(false);
    }
  }

  return (
    <main className="min-h-dvh grid place-items-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-altin text-xs tracking-[0.3em] uppercase mb-2">Rota Performans</div>
          <h1 className="text-2xl font-semibold">Akademi'ye giriş</h1>
        </div>

        <form onSubmit={gonder} className="bg-yuzey border border-cizgi rounded-2xl p-6 space-y-4" noValidate>
          <label className="block">
            <span className="text-sm text-metin-soluk">Telefon veya e-posta</span>
            <input
              className="mt-1 w-full rounded-lg bg-zemin border border-cizgi px-3 py-2.5 outline-none focus:border-altin"
              value={giris}
              onChange={(e) => setGiris(e.target.value)}
              autoComplete="username"
              inputMode="email"
              required
            />
          </label>

          <label className="block">
            <span className="text-sm text-metin-soluk">Şifre</span>
            <input
              className="mt-1 w-full rounded-lg bg-zemin border border-cizgi px-3 py-2.5 outline-none focus:border-altin"
              type="password"
              value={sifre}
              onChange={(e) => setSifre(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>

          {hata && (
            <p role="alert" className="text-sm text-hata">
              {hata}
            </p>
          )}

          <button
            type="submit"
            disabled={gonderiliyor || giris.length < 3 || sifre.length < 1}
            className="w-full rounded-lg bg-altin text-zemin font-semibold py-2.5 hover:bg-altin-acik disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {gonderiliyor ? "Giriş yapılıyor…" : "Giriş yap"}
          </button>
        </form>
      </div>
    </main>
  );
}
