import { useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import BeniHatirla from "../components/BeniHatirla";
import Karsilama from "../components/Karsilama";
import { ApiHata } from "../lib/api";
import { PANEL_YOLU, rolPaneli, type Panel } from "../lib/panel";
import { girisiBicimle, hatirlananiOku, hatirlananiSil, varsayilanHatirla } from "../lib/hatirla";
import { bilgiKutusu, birincilDugme, girdi } from "../lib/stil";

// Teknik destek kendi iki adımlı giriş sayfasını kullanır (DestekGiris).
type GirisPaneli = Exclude<Panel, "destek">;

const BASLIK: Record<GirisPaneli, { baslik: string; karsilama: ReactNode; ipucu: string; yer: string }> = {
  veli: {
    baslik: "Veli / öğrenci girişi",
    karsilama: (
      <>
        Hoş geldiniz,
        <br />
        <span className="vurgu-kalem">havuza</span> bir adım kaldı.
      </>
    ),
    ipucu: "Kulübe kayıtlı telefon numaranızla ve size verilen şifreyle giriş yapın.",
    yer: "05xx xxx xx xx",
  },
  antrenor: { baslik: "Antrenör girişi", karsilama: "İyi dersler.", ipucu: "Kulübün size verdiği giriş bilgileriyle giriş yapın.", yer: "e-posta veya telefon" },
  yonetici: { baslik: "Yönetici girişi", karsilama: "Yönetim paneli.", ipucu: "Yönetici hesabınızla e-posta veya telefon numaranızla giriş yapın.", yer: "E-posta veya telefon" },
};
const DIGER: Record<GirisPaneli, GirisPaneli | null> = { veli: null, antrenor: "yonetici", yonetici: "antrenor" };

export default function Giris({ panel = "veli" }: { panel?: GirisPaneli }) {
  const { kullanici, girisYap, oturumSuresiDoldu } = useAuth();
  const [giris, setGiris] = useState("");
  const [sifre, setSifre] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);
  // Hatırlanan hesap yalnız kendi panelinin giriş sayfasında gösterilir.
  const panelHesabi = () => {
    const h = hatirlananiOku();
    return h && h.panel === panel ? h : null;
  };
  const [hatirlanan, setHatirlanan] = useState(panelHesabi);
  const [beniHatirla, setBeniHatirla] = useState(() => (panelHesabi() ? true : varsayilanHatirla()));

  // Başka panelin hesabıyla açık oturum varken bu panelin giriş sayfası form gösterir (hesap değiştirmek için).
  if (kullanici && rolPaneli(kullanici.rol) === panel) return <Navigate to="/" replace />;

  async function gonder(e: FormEvent) {
    e.preventDefault();
    setHata(null);
    setGonderiliyor(true);
    try {
      await girisYap(hatirlanan ? hatirlanan.giris : giris, sifre, beniHatirla, panel);
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
    <Karsilama baslik={BASLIK[panel].karsilama} aciklama={BASLIK[panel].ipucu}>
      <div>
        <h2 className="mb-3 font-display text-[19px]">{BASLIK[panel].baslik}</h2>
        {hatirlanan ? (
          <form onSubmit={gonder} className="bg-yuzey border border-cizgi rounded-[16px] p-6 space-y-4 shadow-[0_10px_30px_-18px_rgba(0,0,0,0.35)]" noValidate>
            {oturumSuresiDoldu && (
              <p role="status" className={bilgiKutusu}>
                Oturum süreniz doldu, şifrenizle tekrar giriş yapın.
              </p>
            )}
            <div>
              <div className="eyebrow">Tekrar hoş geldiniz</div>
              <div className="mt-1 font-display text-[26px] leading-[1.15] break-words">{girisiBicimle(hatirlanan.ad)}</div>
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
          <form onSubmit={gonder} className="bg-yuzey border border-cizgi rounded-[16px] p-6 space-y-4 shadow-[0_10px_30px_-18px_rgba(0,0,0,0.35)]" noValidate>
            <label className="block">
              <span className="text-[13px] text-metin-soluk">Telefon veya e-posta</span>
              <input
                className={girdi}
                value={giris}
                onChange={(e) => setGiris(e.target.value)}
                autoComplete="username"
                type="text"
                autoCapitalize="none"
                placeholder={BASLIK[panel].yer}
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
        {DIGER[panel] && (
          <p className="mt-5 text-center text-[13px] text-metin-soluk">
            <Link to={PANEL_YOLU[DIGER[panel]!]} className="underline underline-offset-4 hover:text-altin-metin">
              {BASLIK[DIGER[panel]!].baslik}
            </Link>
          </p>
        )}
      </div>
    </Karsilama>
  );
}
