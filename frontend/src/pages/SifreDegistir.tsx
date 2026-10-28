import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import TemaDugmesi from "../components/TemaDugmesi";
import { api, ApiHata } from "../lib/api";
import { yeniSifreHatasi } from "../lib/dogrulama";
import { birincilDugme, dugme, girdi } from "../lib/stil";

type Hatalar = { mevcut?: string; yeni?: string; tekrar?: string };

function dogrula(mevcut: string, yeni: string, tekrar: string): Hatalar {
  const h: Hatalar = {};
  if (!mevcut) h.mevcut = "Geçici şifrenizi girin.";
  const yeniHata = yeniSifreHatasi(mevcut, yeni);
  if (yeniHata) h.yeni = yeniHata;
  if (tekrar !== yeni) h.tekrar = "Şifreler eşleşmiyor.";
  return h;
}

export default function SifreDegistir() {
  const { kullanici, yukleniyor, cikisYap, sifreDegistirildi } = useAuth();
  const gezin = useNavigate();
  const [mevcut, setMevcut] = useState("");
  const [yeni, setYeni] = useState("");
  const [tekrar, setTekrar] = useState("");
  const [hatalar, setHatalar] = useState<Hatalar>({});
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);

  if (yukleniyor) return <div className="min-h-dvh grid place-items-center text-metin-soluk">Yükleniyor…</div>;
  if (!kullanici) return <Navigate to="/giris" replace />;
  if (!kullanici.sifre_degistirmeli) return <Navigate to="/" replace />;

  async function gonder(e: FormEvent) {
    e.preventDefault();
    setHata(null);
    const h = dogrula(mevcut, yeni, tekrar);
    setHatalar(h);
    if (Object.keys(h).length > 0) return;
    setGonderiliyor(true);
    try {
      await api("/api/auth/sifre-degistir", {
        method: "POST",
        body: JSON.stringify({ mevcut_sifre: mevcut, yeni_sifre: yeni }),
      });
      await sifreDegistirildi();
      gezin("/", { replace: true });
    } catch (err) {
      setHata(err instanceof ApiHata ? err.message : "Bağlantı kurulamadı. Lütfen tekrar deneyin.");
    } finally {
      setGonderiliyor(false);
    }
  }

  async function cik() {
    try {
      await cikisYap();
    } finally {
      gezin("/giris", { replace: true });
    }
  }

  const alanHatasi = (m?: string) =>
    m ? (
      <span role="alert" className="mt-1 block text-[13px] text-hata">
        {m}
      </span>
    ) : null;

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
              <h1 className="mt-1 font-display font-medium text-[28px] md:text-[34px] leading-[1.1]">Şifrenizi belirleyin</h1>
          </div>
        </div>

        <form onSubmit={gonder} className="bg-yuzey border border-cizgi rounded-[5px] p-6 space-y-4" noValidate>
          <p className="text-[13px] text-metin-soluk">Geçici şifreyle giriş yaptınız. Devam etmek için kendi şifrenizi belirleyin.</p>

          <div>
            <label className="block">
              <span className="text-[13px] text-metin-soluk">Mevcut (geçici) şifre</span>
              <input className={girdi} type="password" value={mevcut} onChange={(e) => setMevcut(e.target.value)} autoComplete="current-password" autoFocus />
            </label>
            {alanHatasi(hatalar.mevcut)}
          </div>

          <div>
            <label className="block">
              <span className="text-[13px] text-metin-soluk">Yeni şifre</span>
              <input className={girdi} type="password" value={yeni} onChange={(e) => setYeni(e.target.value)} autoComplete="new-password" />
            </label>
            {alanHatasi(hatalar.yeni)}
          </div>

          <div>
            <label className="block">
              <span className="text-[13px] text-metin-soluk">Yeni şifre (tekrar)</span>
              <input className={girdi} type="password" value={tekrar} onChange={(e) => setTekrar(e.target.value)} autoComplete="new-password" />
            </label>
            {alanHatasi(hatalar.tekrar)}
          </div>

          {hata && (
            <p role="alert" className="text-[13px] text-hata">
              {hata}
            </p>
          )}

          <button type="submit" disabled={gonderiliyor} className={`${birincilDugme} w-full`}>
            {gonderiliyor ? "Kaydediliyor…" : "Şifreyi kaydet"}
          </button>
          <button type="button" onClick={() => void cik()} className={`${dugme} w-full`}>
            Çıkış yap
          </button>
        </form>
      </div>
    </main>
  );
}
