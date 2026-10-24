import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import BeniHatirla from "../components/BeniHatirla";
import TemaDugmesi from "../components/TemaDugmesi";
import { ApiHata } from "../lib/api";
import { girisiBicimle, hatirlananiOku, hatirlananiSil, varsayilanHatirla } from "../lib/hatirla";
import { bilgiKutusu, birincilDugme, girdi } from "../lib/stil";

export default function Giris() {
  const { kullanici, girisYap, oturumSuresiDoldu } = useAuth();
  const [giris, setGiris] = useState("");
  const [sifre, setSifre] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);
  const [hatirlanan, setHatirlanan] = useState(hatirlananiOku);
  const [beniHatirla, setBeniHatirla] = useState(() => (hatirlananiOku() ? true : varsayilanHatirla()));

  if (kullanici) return <Navigate to="/" replace />;

  async function gonder(e: FormEvent) {
    e.preventDefault();
    setHata(null);
    setGonderiliyor(true);
    try {
      await girisYap(hatirlanan ? hatirlanan.giris : giris, sifre, beniHatirla);
    } catch (err) {
      setHata(err instanceof ApiHata ? err.message : "Bağlantı kurulamadı. Lütfen tekrar deneyin.");
    } finally {
      setGonderiliyor(false);
    }
  }

  function baskaHesap() {
    hatirlananiSil();
    setHatirlanan(null);
    setBeniHatirla(false);
    setGiris("");
    setSifre("");
    setHata(null);
  }

  return (
    <main className="min-h-dvh grid place-items-center px-4 relative">
      <div className="absolute top-3 right-3">
        <TemaDugmesi />
      </div>
      <div className="w-full max-w-sm">
        <div className="mb-7 flex items-center gap-4">
          <span
            aria-hidden="true"
            className="size-10 rounded-[3px] bg-serit border border-serit-ikon-secili/50 grid place-items-center text-serit-ikon-secili text-xs font-semibold tracking-wider"
          >
            RP
          </span>
          <div>
            <div className="eyebrow">Rota Performans</div>
            <h1 className="mt-1 font-display font-medium text-[28px] md:text-[34px] leading-[1.1]">Akademi'ye giriş</h1>
          </div>
        </div>

        {hatirlanan ? (
          <form onSubmit={gonder} className="bg-yuzey border border-cizgi rounded-[5px] p-6 space-y-4" noValidate>
            {oturumSuresiDoldu && (
              <p role="status" className={bilgiKutusu}>
                Oturum süreniz doldu, şifrenizle tekrar giriş yapın.
              </p>
            )}
            <div>
              <div className="eyebrow">Tekrar hoş geldiniz</div>
              <div className="mt-1 font-display font-medium text-[26px] leading-[1.15] break-words">{girisiBicimle(hatirlanan.ad)}</div>
              {hatirlanan.ad !== hatirlanan.giris && (
                <div className="mt-1 text-[13px] text-metin-soluk break-all">{girisiBicimle(hatirlanan.giris)}</div>
              )}
            </div>

            <label className="block">
              <span className="text-[13px] text-metin-soluk">Şifre</span>
              <input
                className={girdi}
                type="password"
                value={sifre}
                onChange={(e) => setSifre(e.target.value)}
                autoComplete="current-password"
                autoFocus
                required
              />
            </label>

            <BeniHatirla isaretli={beniHatirla} degisti={setBeniHatirla} />

            {hata && (
              <p role="alert" className="text-[13px] text-hata">
                {hata}
              </p>
            )}

            <button type="submit" disabled={gonderiliyor || sifre.length < 1} className={`${birincilDugme} w-full`}>
              {gonderiliyor ? "Giriş yapılıyor…" : "Giriş yap"}
            </button>
            <button
              type="button"
              onClick={baskaHesap}
              className="w-full min-h-11 text-[13px] text-metin-orta underline underline-offset-4 hover:text-altin-metin"
            >
              Başka hesapla giriş yap
            </button>
          </form>
        ) : (
          <form onSubmit={gonder} className="bg-yuzey border border-cizgi rounded-[5px] p-6 space-y-4" noValidate>
            <label className="block">
              <span className="text-[13px] text-metin-soluk">Telefon veya e-posta</span>
              <input
                className={girdi}
                value={giris}
                onChange={(e) => setGiris(e.target.value)}
                autoComplete="username"
                type="text"
                autoCapitalize="none"
                placeholder="05xx xxx xx xx veya e-posta"
                required
              />
            </label>

            <label className="block">
              <span className="text-[13px] text-metin-soluk">Şifre</span>
              <input
                className={girdi}
                type="password"
                value={sifre}
                onChange={(e) => setSifre(e.target.value)}
                autoComplete="current-password"
                required
              />
            </label>

            <BeniHatirla isaretli={beniHatirla} degisti={setBeniHatirla} />

            {hata && (
              <p role="alert" className="text-[13px] text-hata">
                {hata}
              </p>
            )}

            <button type="submit" disabled={gonderiliyor || giris.length < 3 || sifre.length < 1} className={`${birincilDugme} w-full`}>
              {gonderiliyor ? "Giriş yapılıyor…" : "Giriş yap"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
