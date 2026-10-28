import { useEffect, useState, type FormEvent } from "react";
import { profilGetir, profilGuncelle, sifreDegistir, type Profil } from "../api/veli";
import Kart from "../components/Kart";
import SayfaBasligi from "../components/SayfaBasligi";
import TelefonGirdisi from "../components/TelefonGirdisi";
import { hataMesaji, yeniSifreHatasi } from "../lib/dogrulama";
import { apiyeCevir, gecerliMi, rakamlaraCevir, TELEFON_HATA } from "../lib/telefon";
import { basariKutusu, birincilDugme, girdi } from "../lib/stil";

function BilgiFormu({ profil, onKaydet }: { profil: Profil; onKaydet: (p: Profil) => void }) {
  const [ad, setAd] = useState(profil.ad_soyad ?? "");
  const [telefon, setTelefon] = useState(rakamlaraCevir(profil.telefon));
  const [hata, setHata] = useState<string | null>(null);
  const [tamam, setTamam] = useState(false);
  const [mesgul, setMesgul] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    setTamam(false);
    if (!ad.trim()) return setHata("Ad soyad boş olamaz.");
    if (!gecerliMi(telefon)) return setHata(`${TELEFON_HATA}.`);
    setMesgul(true);
    setHata(null);
    try {
      onKaydet(await profilGuncelle({ ad_soyad: ad.trim(), telefon: apiyeCevir(telefon) ?? "" }));
      setTamam(true);
    } catch (err) {
      setHata(hataMesaji(err));
    } finally {
      setMesgul(false);
    }
  }

  return (
    <Kart baslik="Bilgilerim" aciklama="Kulübün sizinle iletişim kurduğu bilgiler">
      <form onSubmit={gonder} noValidate className="space-y-4 max-w-md">
        <label className="block">
          <span className="text-[13px] text-metin-soluk">Giriş bilgisi</span>
          <input className={`${girdi} opacity-70`} value={profil.giris} readOnly aria-readonly="true" />
          <span className="mt-1 block text-xs text-metin-soluk">Giriş bilgisini değiştirmek için kulüple iletişime geçin.</span>
        </label>
        <label className="block">
          <span className="text-[13px] text-metin-soluk">Ad soyad</span>
          <input className={girdi} value={ad} onChange={(e) => setAd(e.target.value)} maxLength={200} autoComplete="name" />
        </label>
        <label className="block">
          <span className="text-[13px] text-metin-soluk">Telefon</span>
          <TelefonGirdisi value={telefon} onChange={setTelefon} />
        </label>
        {hata && (
          <p role="alert" className="text-[13px] text-hata">
            {hata}
          </p>
        )}
        {tamam && (
          <p role="status" className={basariKutusu}>
            Bilgileriniz kaydedildi.
          </p>
        )}
        <button type="submit" disabled={mesgul} className={birincilDugme}>
          {mesgul ? "Kaydediliyor…" : "Bilgileri kaydet"}
        </button>
      </form>
    </Kart>
  );
}

function SifreFormu() {
  const [mevcut, setMevcut] = useState("");
  const [yeni, setYeni] = useState("");
  const [tekrar, setTekrar] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [tamam, setTamam] = useState(false);
  const [mesgul, setMesgul] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    setTamam(false);
    const h = !mevcut ? "Mevcut şifrenizi girin." : yeniSifreHatasi(mevcut, yeni) ?? (tekrar !== yeni ? "Şifreler eşleşmiyor." : null);
    if (h) return setHata(h);
    setMesgul(true);
    setHata(null);
    try {
      await sifreDegistir(mevcut, yeni);
      setMevcut("");
      setYeni("");
      setTekrar("");
      setTamam(true);
    } catch (err) {
      setHata(hataMesaji(err));
    } finally {
      setMesgul(false);
    }
  }

  return (
    <Kart baslik="Şifre değiştir" aciklama="Başka cihazlardaki oturumlar kapatılır">
      <form onSubmit={gonder} noValidate className="space-y-4 max-w-md">
        <label className="block">
          <span className="text-[13px] text-metin-soluk">Mevcut şifre</span>
          <input className={girdi} type="password" value={mevcut} onChange={(e) => setMevcut(e.target.value)} autoComplete="current-password" />
        </label>
        <label className="block">
          <span className="text-[13px] text-metin-soluk">Yeni şifre</span>
          <input className={girdi} type="password" value={yeni} onChange={(e) => setYeni(e.target.value)} autoComplete="new-password" />
        </label>
        <label className="block">
          <span className="text-[13px] text-metin-soluk">Yeni şifre (tekrar)</span>
          <input className={girdi} type="password" value={tekrar} onChange={(e) => setTekrar(e.target.value)} autoComplete="new-password" />
        </label>
        {hata && (
          <p role="alert" className="text-[13px] text-hata">
            {hata}
          </p>
        )}
        {tamam && (
          <p role="status" className={basariKutusu}>
            Şifreniz değiştirildi.
          </p>
        )}
        <button type="submit" disabled={mesgul} className={birincilDugme}>
          {mesgul ? "Kaydediliyor…" : "Şifreyi değiştir"}
        </button>
      </form>
    </Kart>
  );
}

export default function VeliProfil() {
  const [profil, setProfil] = useState<Profil | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    let iptal = false;
    profilGetir()
      .then((p) => !iptal && setProfil(p))
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => {
      iptal = true;
    };
  }, []);

  return (
    <>
      <SayfaBasligi baslik="Profil" />
      {hata && (
        <p role="alert" className="text-sm text-hata">
          {hata}
        </p>
      )}
      {profil && (
        <div className="grid gap-4 lg:grid-cols-2 items-start">
          <BilgiFormu profil={profil} onKaydet={setProfil} />
          <SifreFormu />
        </div>
      )}
    </>
  );
}
