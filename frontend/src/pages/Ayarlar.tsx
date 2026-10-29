import { useEffect, useState, type FormEvent } from "react";
import { ayarlariGetir, ayarlariGuncelle, type Ayarlar as AyarVeri } from "../api/ayarlar";
import { sifreDegistir } from "../api/veli";
import { useAuth } from "../auth/AuthProvider";
import Kart from "../components/Kart";
import SayfaBasligi from "../components/SayfaBasligi";
import TelefonGirdisi from "../components/TelefonGirdisi";
import { hataMesaji, yeniSifreHatasi } from "../lib/dogrulama";
import { apiyeCevir, gecerliMi, rakamlaraCevir, TELEFON_HATA } from "../lib/telefon";
import { basariKutusu, birincilDugme, girdi, hataKutusu } from "../lib/stil";

const etiket = "text-[13px] text-metin-soluk";

function Sonuc({ hata, tamam, mesaj }: { hata: string | null; tamam: boolean; mesaj: string }) {
  return (
    <>
      {hata && <p role="alert" className={hataKutusu}>{hata}</p>}
      {tamam && <p role="status" className={basariKutusu}>{mesaj}</p>}
    </>
  );
}

/** Kaydetme durumu: mesgul/hata/tamam üçlüsü. */
function useKayit() {
  const [mesgul, setMesgul] = useState(false);
  const [hata, setHata] = useState<string | null>(null);
  const [tamam, setTamam] = useState(false);
  async function calistir(is: () => Promise<void>) {
    setMesgul(true);
    setHata(null);
    setTamam(false);
    try {
      await is();
      setTamam(true);
    } catch (err) {
      setHata(hataMesaji(err));
    } finally {
      setMesgul(false);
    }
  }
  return { mesgul, hata, tamam, setHata, calistir };
}

function KulupKarti({ veri, onKaydet }: { veri: AyarVeri; onKaydet: (a: AyarVeri) => void }) {
  const [ad, setAd] = useState(veri.ad);
  const [telefon, setTelefon] = useState(rakamlaraCevir(veri.telefon));
  const [eposta, setEposta] = useState(veri.eposta ?? "");
  const [adres, setAdres] = useState(veri.adres ?? "");
  const k = useKayit();

  function gonder(e: FormEvent) {
    e.preventDefault();
    if (ad.trim().length < 2) return k.setHata("Kulüp adı en az 2 karakter olmalı.");
    if (telefon && !gecerliMi(telefon)) return k.setHata(TELEFON_HATA + ".");
    k.calistir(async () => {
      const a = await ayarlariGuncelle({
        ad: ad.trim(), telefon: apiyeCevir(telefon) ?? "", eposta: eposta.trim(), adres: adres.trim(),
      });
      onKaydet(a);
    });
  }

  return (
    <Kart baslik="Kulüp bilgileri" aciklama="Kulübün iletişim bilgileri">
      <form onSubmit={gonder} noValidate className="space-y-4 max-w-md">
        <label className="block"><span className={etiket}>Kulüp adı</span>
          <input className={girdi} value={ad} maxLength={120} onChange={(e) => setAd(e.target.value)} /></label>
        <label className="block"><span className={etiket}>Telefon (isteğe bağlı)</span>
          <TelefonGirdisi value={telefon} onChange={setTelefon} /></label>
        <label className="block"><span className={etiket}>E-posta (isteğe bağlı)</span>
          <input className={girdi} type="email" autoComplete="off" value={eposta} maxLength={254} onChange={(e) => setEposta(e.target.value)} /></label>
        <label className="block"><span className={etiket}>Adres (isteğe bağlı)</span>
          <textarea className={`${girdi} min-h-20`} value={adres} maxLength={500} onChange={(e) => setAdres(e.target.value)} /></label>
        <Sonuc hata={k.hata} tamam={k.tamam} mesaj="Kulüp bilgileri kaydedildi." />
        <button type="submit" disabled={k.mesgul} className={birincilDugme}>
          {k.mesgul ? "Kaydediliyor…" : "Kulüp bilgilerini kaydet"}
        </button>
      </form>
    </Kart>
  );
}

function BildirimKarti({ veri, onKaydet }: { veri: AyarVeri; onKaydet: (a: AyarVeri) => void }) {
  const [dakika, setDakika] = useState(String(veri.geri_alma_dakika));
  const [esik, setEsik] = useState(String(veri.azaldi_esigi));
  const k = useKayit();

  function gonder(e: FormEvent) {
    e.preventDefault();
    const d = Number(dakika);
    const s = Number(esik);
    if (!Number.isInteger(d) || d < 1 || d > 15) return k.setHata("Bekleme süresi 1 ile 15 dakika arasında olmalı.");
    if (!Number.isInteger(s) || s < 1 || s > 5) return k.setHata("Uyarı eşiği 1 ile 5 ders arasında olmalı.");
    k.calistir(async () => {
      onKaydet(await ayarlariGuncelle({ geri_alma_dakika: d, azaldi_esigi: s }));
    });
  }

  return (
    <Kart baslik="Bildirim ayarları" aciklama="Velilere giden bildirimlerin zamanlaması">
      <form onSubmit={gonder} noValidate className="space-y-4 max-w-md">
        <label className="block"><span className={etiket}>Devamsızlık bildirimi bekleme süresi (dakika)</span>
          <input className={girdi} type="number" min={1} max={15} inputMode="numeric" value={dakika} onChange={(e) => setDakika(e.target.value)} aria-describedby="bekleme-ipucu" /></label>
        <p id="bekleme-ipucu" className="-mt-2 text-[12px] text-metin-soluk">
          Yoklama yanlış işaretlenirse bu süre içinde düzeltilebilir; bildirim süre dolunca gider (1–15).
        </p>
        <label className="block"><span className={etiket}>“Ders hakkı azaldı” uyarısı (kalan ders)</span>
          <input className={girdi} type="number" min={1} max={5} inputMode="numeric" value={esik} onChange={(e) => setEsik(e.target.value)} aria-describedby="esik-ipucu" /></label>
        <p id="esik-ipucu" className="-mt-2 text-[12px] text-metin-soluk">Kalan ders hakkı bu sayıya düşünce veli uyarılır (1–5).</p>
        <Sonuc hata={k.hata} tamam={k.tamam} mesaj="Bildirim ayarları kaydedildi." />
        <button type="submit" disabled={k.mesgul} className={birincilDugme}>
          {k.mesgul ? "Kaydediliyor…" : "Bildirim ayarlarını kaydet"}
        </button>
      </form>
    </Kart>
  );
}

function HesapKarti() {
  const { kullanici } = useAuth();
  const [mevcut, setMevcut] = useState("");
  const [yeni, setYeni] = useState("");
  const [tekrar, setTekrar] = useState("");
  const k = useKayit();

  function gonder(e: FormEvent) {
    e.preventDefault();
    const h = !mevcut ? "Mevcut şifrenizi girin." : yeniSifreHatasi(mevcut, yeni) ?? (tekrar !== yeni ? "Şifreler eşleşmiyor." : null);
    if (h) return k.setHata(h);
    k.calistir(async () => {
      await sifreDegistir(mevcut, yeni);
      setMevcut("");
      setYeni("");
      setTekrar("");
    });
  }

  return (
    <Kart baslik="Hesabım" aciklama="Şifre değişince diğer cihazlardaki oturumlar kapatılır">
      <form onSubmit={gonder} noValidate className="space-y-4 max-w-md">
        <label className="block"><span className={etiket}>Giriş</span>
          <input className={`${girdi} opacity-70`} value={kullanici?.giris ?? ""} readOnly /></label>
        <label className="block"><span className={etiket}>Mevcut şifre</span>
          <input className={girdi} type="password" value={mevcut} onChange={(e) => setMevcut(e.target.value)} autoComplete="current-password" /></label>
        <label className="block"><span className={etiket}>Yeni şifre</span>
          <input className={girdi} type="password" value={yeni} onChange={(e) => setYeni(e.target.value)} autoComplete="new-password" /></label>
        <label className="block"><span className={etiket}>Yeni şifre (tekrar)</span>
          <input className={girdi} type="password" value={tekrar} onChange={(e) => setTekrar(e.target.value)} autoComplete="new-password" /></label>
        <Sonuc hata={k.hata} tamam={k.tamam} mesaj="Şifreniz değiştirildi." />
        <button type="submit" disabled={k.mesgul} className={birincilDugme}>
          {k.mesgul ? "Kaydediliyor…" : "Şifreyi değiştir"}
        </button>
      </form>
    </Kart>
  );
}

export default function Ayarlar() {
  const [veri, setVeri] = useState<AyarVeri | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    let iptal = false;
    ayarlariGetir()
      .then((a) => !iptal && setVeri(a))
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => {
      iptal = true;
    };
  }, []);

  return (
    <>
      <SayfaBasligi baslik="Ayarlar" />
      {hata && <p role="alert" className="text-sm text-hata">{hata}</p>}
      <div className="grid gap-4 lg:grid-cols-2 items-start">
        {veri && <KulupKarti veri={veri} onKaydet={setVeri} />}
        {veri && <BildirimKarti veri={veri} onKaydet={setVeri} />}
        <HesapKarti />
      </div>
    </>
  );
}
