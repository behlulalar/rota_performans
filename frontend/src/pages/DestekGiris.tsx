import { useEffect, useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import { ikiAdimDogrula, ikiAdimKurulumu, ikiAdimKurulumuDogrula, type KurulumBilgisi } from "../api/ikiAdim";
import { useAuth } from "../auth/AuthProvider";
import BeniHatirla from "../components/BeniHatirla";
import Karsilama from "../components/Karsilama";
import TelefonGirdisi from "../components/TelefonGirdisi";
import { gecerliMi, numaraCoz } from "../lib/telefon";
import { ApiHata } from "../lib/api";
import { hataMesaji } from "../lib/dogrulama";
import { hatirlananiOku, varsayilanHatirla } from "../lib/hatirla";
import { rolPaneli } from "../lib/panel";
import { birincilDugme, dugme, girdi, uyariKutusu } from "../lib/stil";

const KART = "bg-yuzey border border-cizgi rounded-[16px] p-6 space-y-4 shadow-[0_10px_30px_-18px_rgba(0,0,0,0.35)]";
const KOD_HATASI = "Doğrulama kodu hatalı";

type Adim =
  | { ad: "sifre" }
  | { ad: "kurulum"; belirtec: string; bilgi: KurulumBilgisi | null }
  | { ad: "dogrulama"; belirtec: string; kurtarma: boolean }
  | { ad: "kodlar"; erisim: string; kodlar: string[] };

const ACIKLAMA: Record<Adim["ad"], string> = {
  sifre: "Teknik destek hesabıyla giriş yapın. Şifrenin ardından doğrulama kodu istenir.",
  kurulum: "Hesabınızı korumak için kimlik doğrulama uygulamasını bir kez eşleştirin.",
  dogrulama: "Kimlik doğrulama uygulamanızdaki 6 haneli kodu girin.",
  kodlar: "Kurtarma kodlarını güvenli bir yere kaydedin.",
};

// Gizli anahtar okunaklı olsun diye dörderli gruplanır.
const gruplu = (a: string) => a.replace(/\s/g, "").replace(/(.{4})(?=.)/g, "$1 ");

export default function DestekGiris() {
  const { kullanici, girisYap, belirtecleGiris } = useAuth();
  const [adim, setAdim] = useState<Adim>({ ad: "sifre" });
  // Bu cihazda hatırlanan destek hesabı varsa giriş alanı dolu gelir (yalnız kod ve şifre sorulur).
  const [giris, setGiris] = useState(() => {
    const h = hatirlananiOku();
    return h?.panel === "destek" ? numaraCoz(h.giris) : "";
  });
  const [beniHatirla, setBeniHatirla] = useState(() => hatirlananiOku()?.panel === "destek" || varsayilanHatirla());
  const [sifre, setSifre] = useState("");
  const [kod, setKod] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);
  const [kopyalandi, setKopyalandi] = useState(false);

  // Kurulum adımı açılınca gizli anahtar sunucudan alınır (kod doğrulanana kadar etkin değildir).
  const kurulumBelirteci = adim.ad === "kurulum" ? adim.belirtec : null;
  useEffect(() => {
    if (!kurulumBelirteci) return;
    let iptal = false;
    ikiAdimKurulumu(kurulumBelirteci)
      .then((b) => !iptal && setAdim((a) => (a.ad === "kurulum" ? { ...a, bilgi: b } : a)))
      .catch((e) => !iptal && sifreyeDon(e));
    return () => {
      iptal = true;
    };
  }, [kurulumBelirteci]);

  // Kurtarma kodları gösterilirken oturum henüz açılmadı; açıldığında panele geçilir.
  if (kullanici && rolPaneli(kullanici.rol) === "destek") return <Navigate to="/" replace />;

  /** Bekleyen belirteç süresi dolduysa ya da hesap kilitlendiyse şifre adımına dönülür. */
  function sifreyeDon(err: unknown) {
    setAdim({ ad: "sifre" });
    setSifre("");
    setKod("");
    setHata(hataMesaji(err));
  }

  function adimHatasi(err: unknown) {
    if (err instanceof ApiHata && err.durum === 401 && err.message !== KOD_HATASI) return sifreyeDon(err);
    setHata(err instanceof ApiHata ? err.message : "Bağlantı kurulamadı. Lütfen tekrar deneyin.");
  }

  async function sifreGonder(e: FormEvent) {
    e.preventDefault();
    setHata(null);
    setGonderiliyor(true);
    try {
      const sonuc = await girisYap(giris, sifre, beniHatirla, "destek");
      if (sonuc) {
        setKod("");
        setAdim(
          sonuc.durum === "kurulum"
            ? { ad: "kurulum", belirtec: sonuc.bekleyen_belirtec, bilgi: null }
            : { ad: "dogrulama", belirtec: sonuc.bekleyen_belirtec, kurtarma: false },
        );
      }
    } catch (err) {
      setHata(err instanceof ApiHata ? err.message : "Bağlantı kurulamadı. Lütfen tekrar deneyin.");
    } finally {
      setGonderiliyor(false);
    }
  }

  async function kodGonder(e: FormEvent) {
    e.preventDefault();
    if (adim.ad !== "kurulum" && adim.ad !== "dogrulama") return;
    setHata(null);
    setGonderiliyor(true);
    try {
      if (adim.ad === "kurulum") {
        const s = await ikiAdimKurulumuDogrula(adim.belirtec, kod.trim());
        setKod("");
        setAdim({ ad: "kodlar", erisim: s.access_token, kodlar: s.kurtarma_kodlari });
      } else {
        const s = await ikiAdimDogrula(adim.belirtec, kod.trim());
        await belirtecleGiris(s.access_token, beniHatirla, "destek");
      }
    } catch (err) {
      adimHatasi(err);
    } finally {
      setGonderiliyor(false);
    }
  }

  async function devamEt() {
    if (adim.ad !== "kodlar") return;
    setHata(null);
    setGonderiliyor(true);
    try {
      await belirtecleGiris(adim.erisim, beniHatirla, "destek");
    } catch (err) {
      setHata(hataMesaji(err));
      setGonderiliyor(false);
    }
  }

  async function kodlariKopyala(kodlar: string[]) {
    try {
      await navigator.clipboard.writeText(kodlar.join("\n"));
      setKopyalandi(true);
    } catch {
      setKopyalandi(false);
    }
  }

  function kodlariIndir(kodlar: string[]) {
    const metin = [
      "Rota Performans Akademi - Teknik destek kurtarma kodları",
      "Her kod yalnızca bir kez kullanılabilir. Güvenli bir yerde saklayın.",
      "",
      ...kodlar,
      "",
    ].join("\n");
    const adres = URL.createObjectURL(new Blob([metin], { type: "text/plain;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = adres;
    a.download = "rota-kurtarma-kodlari.txt";
    a.click();
    URL.revokeObjectURL(adres);
  }

  const hataSatiri = hata && (
    <p role="alert" className="text-[13px] text-hata">
      {hata}
    </p>
  );

  return (
    <Karsilama baslik="Teknik destek." aciklama={ACIKLAMA[adim.ad]} arkaPlan>
      <div>
        <h2 className="mb-3 font-display text-[19px]">Teknik destek girişi</h2>

        {adim.ad === "sifre" && (
          <form onSubmit={sifreGonder} className={KART} noValidate>
            <div>
              <span id="giris-telefon-etiketi" className="text-[13px] text-metin-soluk">Telefon numarası</span>
              <TelefonGirdisi value={giris} onChange={setGiris} aria-labelledby="giris-telefon-etiketi" autoFocus />
            </div>
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
            {hataSatiri}
            <button type="submit" disabled={gonderiliyor || !gecerliMi(giris) || sifre.length < 1} className={`${birincilDugme} w-full`}>
              {gonderiliyor ? "Giriş yapılıyor…" : "Devam et"}
            </button>
          </form>
        )}

        {adim.ad === "kurulum" && (
          <form onSubmit={kodGonder} className={KART} noValidate>
            <div>
              <div className="eyebrow">İki adımlı doğrulama kurulumu</div>
              <ol className="mt-2 list-decimal pl-5 space-y-1 text-[13px] text-metin-orta">
                <li>Kimlik doğrulama uygulamasında (Google Authenticator, Microsoft Authenticator vb.) yeni hesap ekleyin.</li>
                <li>Aşağıdaki QR kodu okutun ya da anahtarı elle girin.</li>
                <li>Uygulamanın gösterdiği 6 haneli kodu yazın.</li>
              </ol>
            </div>
            {adim.bilgi ? (
              <>
                {/* QR kodu her temada okunabilsin diye beyaz zeminde çizilir. */}
                <div className="mx-auto w-fit rounded-[12px] bg-white p-3" data-testid="qr-kodu">
                  <QRCodeSVG value={adim.bilgi.otpauth_uri} size={176} marginSize={0} title="İki adımlı doğrulama QR kodu" />
                </div>
                <div>
                  <span className="text-[13px] text-metin-soluk">Elle girilecek anahtar</span>
                  <code
                    data-testid="gizli-anahtar"
                    aria-label="Gizli anahtar"
                    className="mt-1 block break-all rounded-[10px] bg-zemin border border-cizgi-guclu px-3 py-2.5 font-mono text-altin-metin select-all"
                  >
                    {gruplu(adim.bilgi.gizli_anahtar)}
                  </code>
                </div>
              </>
            ) : (
              !hata && <p className="py-6 text-center text-metin-soluk">Kurulum hazırlanıyor…</p>
            )}
            <label className="block">
              <span className="text-[13px] text-metin-soluk">Doğrulama kodu</span>
              <input
                className={`${girdi} num tracking-[0.3em]`}
                value={kod}
                onChange={(e) => setKod(e.target.value.replace(/\D/g, "").slice(0, 6))}
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="123456"
                maxLength={6}
              />
            </label>
            {hataSatiri}
            <button type="submit" disabled={gonderiliyor || !adim.bilgi || kod.length !== 6} className={`${birincilDugme} w-full`}>
              {gonderiliyor ? "Doğrulanıyor…" : "Kurulumu tamamla"}
            </button>
          </form>
        )}

        {adim.ad === "dogrulama" && (
          <form onSubmit={kodGonder} className={KART} noValidate>
            {adim.kurtarma ? (
              <label className="block">
                <span className="text-[13px] text-metin-soluk">Kurtarma kodu</span>
                <input
                  className={`${girdi} num`}
                  value={kod}
                  onChange={(e) => setKod(e.target.value)}
                  autoComplete="off"
                  autoCapitalize="none"
                  placeholder="xxxxx-xxxxx"
                  autoFocus
                />
              </label>
            ) : (
              <label className="block">
                <span className="text-[13px] text-metin-soluk">Doğrulama kodu</span>
                <input
                  className={`${girdi} num tracking-[0.3em]`}
                  value={kod}
                  onChange={(e) => setKod(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  placeholder="123456"
                  maxLength={6}
                  autoFocus
                />
              </label>
            )}
            {hataSatiri}
            <button
              type="submit"
              disabled={gonderiliyor || (adim.kurtarma ? kod.trim().length < 6 : kod.length !== 6)}
              className={`${birincilDugme} w-full`}
            >
              {gonderiliyor ? "Doğrulanıyor…" : "Giriş yap"}
            </button>
            <button
              type="button"
              onClick={() => {
                setAdim({ ...adim, kurtarma: !adim.kurtarma });
                setKod("");
                setHata(null);
              }}
              className="w-full min-h-11 text-[13px] text-metin-orta underline underline-offset-4 hover:text-altin-metin"
            >
              {adim.kurtarma ? "Doğrulama uygulamasındaki kodu kullan" : "Kurtarma kodu kullan"}
            </button>
          </form>
        )}

        {adim.ad === "kodlar" && (
          <div className={KART}>
            <div>
              <div className="eyebrow">İki adımlı doğrulama etkin</div>
              <h3 className="mt-1 font-display text-[22px] leading-[1.15]">Kurtarma kodlarınız</h3>
            </div>
            <p className={uyariKutusu}>
              Bu kodlar yalnızca bir kez gösterilir. Telefonunuza erişemezseniz her kod bir kez kullanılabilir; güvenli bir yere kaydedin.
            </p>
            <ul data-testid="kurtarma-kodlari" className="grid grid-cols-2 gap-2">
              {adim.kodlar.map((k) => (
                <li key={k} className="rounded-[10px] bg-zemin border border-cizgi-guclu px-3 py-2 text-center font-mono text-[14px] text-altin-metin select-all">
                  {k}
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => void kodlariKopyala(adim.kodlar)} className={`${dugme} flex-1`}>
                {kopyalandi ? "Kopyalandı" : "Kopyala"}
              </button>
              <button type="button" onClick={() => kodlariIndir(adim.kodlar)} className={`${dugme} flex-1`}>
                .txt indir
              </button>
            </div>
            {hataSatiri}
            <button type="button" disabled={gonderiliyor} onClick={() => void devamEt()} className={`${birincilDugme} w-full`}>
              {gonderiliyor ? "Açılıyor…" : "Kaydettim, devam et"}
            </button>
          </div>
        )}
      </div>
    </Karsilama>
  );
}
