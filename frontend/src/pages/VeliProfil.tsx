import { useEffect, useState, type FormEvent } from "react";
import {
  bildirimTercihleriGetir,
  bildirimTercihleriKaydet,
  profilGetir,
  profilGuncelle,
  type BildirimTercihYaniti,
  type BildirimTercihleri,
  type Profil,
} from "../api/veli";
import { pushAc, pushDurumuBul, pushKapat, type PushDurumu } from "../lib/push";
import Kart from "../components/Kart";
import SayfaBasligi from "../components/SayfaBasligi";
import YaziBoyutuSecici from "../components/YaziBoyutuSecici";
import TelefonGirdisi from "../components/TelefonGirdisi";
import SifreKarti from "../components/SifreKarti";
import { hataMesaji } from "../lib/dogrulama";
import { apiyeCevir, gecerliMi, numaraCoz, TELEFON_HATA } from "../lib/telefon";
import { basariKutusu, birincilDugme, dugme, girdi } from "../lib/stil";

function BilgiFormu({ profil, onKaydet }: { profil: Profil; onKaydet: (p: Profil) => void }) {
  const [ad, setAd] = useState(profil.ad_soyad ?? "");
  const [telefon, setTelefon] = useState(numaraCoz(profil.telefon));
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

const TERCIH_SATIRLARI: { anahtar: keyof BildirimTercihleri; etiket: string }[] = [
  { anahtar: "ders_gelmedi", etiket: "Devamsızlık bildirimi" },
  { anahtar: "ders_hakki", etiket: "Ders hakkı hatırlatmaları" },
  { anahtar: "whatsapp", etiket: "WhatsApp ile" },
  { anahtar: "push", etiket: "Uygulama bildirimi (push)" },
];

function BildirimFormu() {
  const [tercih, setTercih] = useState<BildirimTercihYaniti | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [tamam, setTamam] = useState(false);
  const [mesgul, setMesgul] = useState(false);

  useEffect(() => {
    let iptal = false;
    bildirimTercihleriGetir()
      .then((t) => !iptal && setTercih(t))
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => {
      iptal = true;
    };
  }, []);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    if (!tercih) return;
    setTamam(false);
    setMesgul(true);
    setHata(null);
    try {
      const { ders_gelmedi, ders_hakki, whatsapp, push } = tercih;
      setTercih(await bildirimTercihleriKaydet({ ders_gelmedi, ders_hakki, whatsapp, push }));
      setTamam(true);
    } catch (err) {
      setHata(hataMesaji(err));
    } finally {
      setMesgul(false);
    }
  }

  return (
    <Kart baslik="Bildirimler" aciklama="Hangi bildirimleri, hangi yoldan almak istediğiniz">
      <form onSubmit={gonder} className="space-y-3 max-w-md">
        {tercih && (
          <>
            {TERCIH_SATIRLARI.map(({ anahtar, etiket }) => (
              <label key={anahtar} className="flex items-center gap-3 min-h-11 text-sm">
                <input
                  type="checkbox"
                  className="size-4"
                  checked={tercih[anahtar]}
                  onChange={(e) => {
                    setTamam(false);
                    setTercih({ ...tercih, [anahtar]: e.target.checked });
                  }}
                />
                {etiket}
              </label>
            ))}
            {!tercih.whatsapp_izni_var && (
              <p className="text-xs text-metin-soluk">
                WhatsApp mesajları için kulübün iletişim izninizi kaydetmiş olması gerekir. İzin verilmediği sürece
                WhatsApp mesajı gönderilmez.
              </p>
            )}
          </>
        )}
        {hata && (
          <p role="alert" className="text-[13px] text-hata">
            {hata}
          </p>
        )}
        {tamam && (
          <p role="status" className={basariKutusu}>
            Bildirim tercihleriniz kaydedildi.
          </p>
        )}
        <button type="submit" disabled={mesgul || !tercih} className={birincilDugme}>
          {mesgul ? "Kaydediliyor…" : "Tercihleri kaydet"}
        </button>
      </form>
      <CihazBildirimi />
    </Kart>
  );
}

const PUSH_METINLERI: Record<PushDurumu, string> = {
  kontrol: "Kontrol ediliyor…",
  desteklenmiyor: "Bu tarayıcı uygulama bildirimlerini desteklemiyor.",
  "ios-ana-ekran": "iPhone'da bildirim almak için önce uygulamayı ana ekrana ekleyin, sonra buradan açın.",
  "yalniz-kurulu": "Bildirimler yalnızca yüklü (yayındaki) uygulamada açılabilir.",
  "sunucu-kapali": "Uygulama bildirimleri şu an kulüp tarafında etkin değil.",
  reddedildi: "Bildirim izni reddedildi. Tarayıcı ayarlarından bu site için izin vermeniz gerekir.",
  kapali: "Bu cihazda bildirimler kapalı.",
  acik: "Bu cihazda bildirimler açık.",
};

function CihazBildirimi() {
  const [durum, setDurum] = useState<PushDurumu>("kontrol");
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);

  useEffect(() => {
    let iptal = false;
    pushDurumuBul()
      .then((d) => !iptal && setDurum(d))
      .catch(() => !iptal && setDurum("desteklenmiyor"));
    return () => {
      iptal = true;
    };
  }, []);

  async function degistir(ac: boolean) {
    setMesgul(true);
    setHata(null);
    try {
      setDurum(ac ? await pushAc() : await pushKapat());
    } catch (err) {
      setHata(hataMesaji(err));
    } finally {
      setMesgul(false);
    }
  }

  return (
    <div className="space-y-2 max-w-md border-t border-cizgi pt-4 mt-4" data-testid="cihaz-bildirimi">
      <h3 className="text-sm font-medium">Bu cihaz</h3>
      <p className="text-[13px] text-metin-soluk">{PUSH_METINLERI[durum]}</p>
      {hata && (
        <p role="alert" className="text-[13px] text-hata">
          {hata}
        </p>
      )}
      {durum === "kapali" && (
        <button type="button" disabled={mesgul} onClick={() => degistir(true)} className={birincilDugme}>
          {mesgul ? "Açılıyor…" : "Bu cihazda bildirimleri aç"}
        </button>
      )}
      {durum === "acik" && (
        <button type="button" disabled={mesgul} onClick={() => degistir(false)} className={dugme}>
          {mesgul ? "Kapatılıyor…" : "Bu cihazda kapat"}
        </button>
      )}
    </div>
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
          <BildirimFormu />
          <SifreKarti />
          <GorunumKarti />
        </div>
      )}
    </>
  );
}
