import { useEffect, useState, type FormEvent } from "react";
import { antrenorProfilGetir, antrenorProfilGuncelle, type AntrenorProfil as Profil } from "../api/antrenorPaneli";
import { useAuth } from "../auth/AuthProvider";
import Kart from "../components/Kart";
import SayfaBasligi from "../components/SayfaBasligi";
import SifreKarti from "../components/SifreKarti";
import TelefonGirdisi from "../components/TelefonGirdisi";
import YaziBoyutuSecici from "../components/YaziBoyutuSecici";
import { hataMesaji } from "../lib/dogrulama";
import { basariKutusu, birincilDugme, girdi } from "../lib/stil";
import { apiyeCevir, gecerliMi, numaraCoz, TELEFON_HATA } from "../lib/telefon";

function BilgiFormu({ profil, onKaydet }: { profil: Profil; onKaydet: (p: Profil) => void }) {
  // Üst çubuktaki ad güncellensin diye kullanıcı sunucudan yeniden okunur.
  const { sifreDegistirildi: kullaniciyiYenile } = useAuth();
  const [ad, setAd] = useState(profil.ad_soyad);
  const [telefon, setTelefon] = useState(numaraCoz(profil.telefon));
  const [hata, setHata] = useState<string | null>(null);
  const [tamam, setTamam] = useState(false);
  const [mesgul, setMesgul] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    setTamam(false);
    if (!ad.trim()) return setHata("Ad soyad boş olamaz.");
    // Telefon isteğe bağlıdır; yazıldıysa geçerli olmalı.
    if (telefon && !gecerliMi(telefon)) return setHata(`${TELEFON_HATA}.`);
    setMesgul(true);
    setHata(null);
    try {
      const yeni = await antrenorProfilGuncelle({ ad_soyad: ad.trim(), telefon: apiyeCevir(telefon) ?? "" });
      onKaydet(yeni);
      setAd(yeni.ad_soyad);
      setTamam(true);
      void kullaniciyiYenile();
    } catch (err) {
      setHata(hataMesaji(err));
    } finally {
      setMesgul(false);
    }
  }

  return (
    <Kart baslik="Bilgilerim" aciklama="Kulübün sizinle iletişim kurduğu bilgiler">
      <form onSubmit={gonder} noValidate className="space-y-4">
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

function GorunumKarti() {
  return (
    <Kart baslik="Görünüm" aciklama="Yazı ve arayüz boyutu">
      <YaziBoyutuSecici />
      <p className="mt-3 text-sm text-metin-soluk">Bu ayar yalnızca bu cihazda geçerlidir.</p>
    </Kart>
  );
}

export default function AntrenorProfil() {
  const [profil, setProfil] = useState<Profil | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    let iptal = false;
    antrenorProfilGetir()
      .then((p) => !iptal && setProfil(p))
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => {
      iptal = true;
    };
  }, []);

  return (
    <>
      <SayfaBasligi baslik="Profilim" />
      {hata && (
        <p role="alert" className="text-sm text-hata">
          {hata}
        </p>
      )}
      {profil && (
        <div className="grid gap-4 lg:grid-cols-2">
          <BilgiFormu profil={profil} onKaydet={setProfil} />
          <SifreKarti tamGenislik />
          <div className="lg:col-span-2">
            <GorunumKarti />
          </div>
        </div>
      )}
    </>
  );
}
