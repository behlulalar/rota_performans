import { useEffect, useState, type FormEvent } from "react";
import { ayarlariGetir, ayarlariGuncelle, type Ayarlar as AyarVeri } from "../api/ayarlar";
import { girisDegistir, telefonDegistir } from "../api/yonetici";
import { sifreDegistir } from "../api/veli";
import { hatirlananiKaydet, hatirlananiOku } from "../lib/hatirla";
import { useAuth } from "../auth/AuthProvider";
import Kart from "../components/Kart";
import SayfaBasligi from "../components/SayfaBasligi";
import YaziBoyutuSecici from "../components/YaziBoyutuSecici";
import TelefonGirdisi from "../components/TelefonGirdisi";
import { hataMesaji, yeniSifreHatasi } from "../lib/dogrulama";
import { apiyeCevir, gecerliMi, numaraCoz, TELEFON_HATA } from "../lib/telefon";
import { birincilDugme, girdi } from "../lib/stil";
import { etiket, Sonuc, useKayit } from "../components/KayitYardimcilari";

function KulupKarti({ veri, onKaydet }: { veri: AyarVeri; onKaydet: (a: AyarVeri) => void }) {
  const [ad, setAd] = useState(veri.ad);
  const [telefon, setTelefon] = useState(numaraCoz(veri.telefon));
  const [eposta, setEposta] = useState(veri.eposta ?? "");
  const [adres, setAdres] = useState(veri.adres ?? "");
  const [instagram, setInstagram] = useState(veri.instagram ?? "");
  const k = useKayit();

  function gonder(e: FormEvent) {
    e.preventDefault();
    if (ad.trim().length < 2) return k.setHata("Kulüp adı en az 2 karakter olmalı.");
    if (telefon && !gecerliMi(telefon)) return k.setHata(TELEFON_HATA + ".");
    k.calistir(async () => {
      const a = await ayarlariGuncelle({
        ad: ad.trim(), telefon: apiyeCevir(telefon) ?? "", eposta: eposta.trim(), adres: adres.trim(), instagram: instagram.trim(),
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
        <label className="block"><span className={etiket}>Instagram (isteğe bağlı)</span>
          <input className={girdi} autoComplete="off" placeholder="kullanıcı adı veya profil bağlantısı" value={instagram} maxLength={200} onChange={(e) => setInstagram(e.target.value)} />
          <span className="mt-1 block text-[12px] text-metin-soluk">Veli panelinde ve veli giriş sayfasında "Bizi takip edin" olarak görünür.</span></label>
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

function GorunumKarti() {
  return (
    <Kart baslik="Görünüm" aciklama="Yazı ve arayüz boyutu">
      <YaziBoyutuSecici />
      <p className="mt-3 text-sm text-metin-soluk">Bu ayar yalnızca bu cihazda geçerlidir.</p>
    </Kart>
  );
}

function GirisFormu() {
  const { kullanici, sifreDegistirildi: kullaniciyiYenile } = useAuth();
  const [yeni, setYeni] = useState(kullanici?.giris ?? "");
  const [sifre, setSifre] = useState("");
  const k = useKayit();

  function gonder(e: FormEvent) {
    e.preventDefault();
    if (!yeni.trim()) return k.setHata("Giriş bilgisi boş olamaz.");
    if (yeni.trim().toLowerCase() === kullanici?.giris) return k.setHata("Yeni giriş bilgisi mevcut olanla aynı.");
    if (!sifre) return k.setHata("Onay için şifrenizi girin.");
    k.calistir(async () => {
      const eski = kullanici?.giris;
      const y = await girisDegistir(yeni.trim(), sifre);
      // Hatırlanan hesap bu hesapsa yeni girişle güncellenir; yoksa giriş ekranı eski bilgiyi gösterirdi.
      const h = hatirlananiOku();
      if (h && h.giris === eski) hatirlananiKaydet({ ...h, giris: y.giris });
      setSifre("");
      setYeni(y.giris);
      await kullaniciyiYenile();
    });
  }

  return (
    <form onSubmit={gonder} noValidate className="space-y-4 max-w-md pb-5 mb-5 border-b border-cizgi">
      <label className="block"><span className={etiket}>Giriş (e-posta veya telefon)</span>
        <input className={girdi} value={yeni} onChange={(e) => setYeni(e.target.value)} autoCapitalize="none" autoComplete="username" /></label>
      <label className="block"><span className={etiket}>Şifreniz (onay için)</span>
        <input className={girdi} type="password" value={sifre} onChange={(e) => setSifre(e.target.value)} autoComplete="current-password" /></label>
      <p className="-mt-2 text-[12px] text-metin-soluk">Giriş değişince diğer cihazlardaki oturumlar kapatılır.</p>
      <Sonuc hata={k.hata} tamam={k.tamam} mesaj="Giriş bilginiz değiştirildi." />
      <button type="submit" disabled={k.mesgul} className={birincilDugme}>
        {k.mesgul ? "Kaydediliyor…" : "Girişi değiştir"}
      </button>
    </form>
  );
}

function TelefonFormu() {
  const { kullanici, sifreDegistirildi: kullaniciyiYenile } = useAuth();
  const [telefon, setTelefon] = useState(numaraCoz(kullanici?.telefon));
  const [sifre, setSifre] = useState("");
  const k = useKayit();

  function gonder(e: FormEvent) {
    e.preventDefault();
    if (telefon && !gecerliMi(telefon)) return k.setHata(TELEFON_HATA + ".");
    if ((apiyeCevir(telefon) ?? null) === (kullanici?.telefon ?? null)) return k.setHata("Telefon bilgisi değişmedi.");
    if (!sifre) return k.setHata("Onay için şifrenizi girin.");
    k.calistir(async () => {
      await telefonDegistir(apiyeCevir(telefon), sifre);
      setSifre("");
      await kullaniciyiYenile();
    });
  }

  return (
    <form onSubmit={gonder} noValidate className="space-y-4 max-w-md pb-5 mb-5 border-b border-cizgi">
      <label className="block"><span className={etiket}>Telefon numaram (isteğe bağlı)</span>
        <TelefonGirdisi value={telefon} onChange={setTelefon} /></label>
      <label className="block"><span className={etiket}>Şifreniz (telefon onayı için)</span>
        <input className={girdi} type="password" value={sifre} onChange={(e) => setSifre(e.target.value)} autoComplete="current-password" /></label>
      <p className="-mt-2 text-[12px] text-metin-soluk">Telefonunuzla da giriş yapabilirsiniz. Boş bırakıp kaydederseniz kaldırılır; diğer cihazlardaki oturumlar kapatılır.</p>
      <Sonuc hata={k.hata} tamam={k.tamam} mesaj="Telefon bilginiz kaydedildi." />
      <button type="submit" disabled={k.mesgul} className={birincilDugme}>
        {k.mesgul ? "Kaydediliyor…" : "Telefonu kaydet"}
      </button>
    </form>
  );
}

function HesapKarti() {
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
    <Kart baslik="Hesabım" aciklama="Giriş bilgisi ve şifre; değişince diğer cihazlardaki oturumlar kapatılır">
      <GirisFormu />
      <TelefonFormu />
      <form onSubmit={gonder} noValidate className="space-y-4 max-w-md">
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
        <GorunumKarti />
      </div>
    </>
  );
}
