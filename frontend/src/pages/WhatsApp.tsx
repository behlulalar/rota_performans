import { useEffect, useState, type FormEvent } from "react";
import { ayarlariGetir, ayarlariGuncelle, type Ayarlar as AyarVeri } from "../api/ayarlar";
import Kart from "../components/Kart";
import { etiket, Sonuc, useKayit } from "../components/KayitYardimcilari";
import SayfaBasligi from "../components/SayfaBasligi";
import WhatsAppBaglantisi from "../components/WhatsAppBaglantisi";
import { hataMesaji } from "../lib/dogrulama";
import { birincilDugme, girdi } from "../lib/stil";

function WhatsAppGonderimKarti({ veri, onKaydet }: { veri: AyarVeri; onKaydet: (a: AyarVeri) => void }) {
  const [saatlik, setSaatlik] = useState(String(veri.wa_saatlik_limit));
  const [gunluk, setGunluk] = useState(String(veri.wa_gunluk_limit));
  const [baslangic, setBaslangic] = useState(String(veri.wa_baslangic_saat));
  const [bitis, setBitis] = useState(String(veri.wa_bitis_saat));
  const [atla, setAtla] = useState(veri.wa_push_varsa_atla);
  const k = useKayit();

  function gonder(e: FormEvent) {
    e.preventDefault();
    const sl = Number(saatlik);
    const gl = Number(gunluk);
    const b = Number(baslangic);
    const s = Number(bitis);
    if (!Number.isInteger(sl) || sl < 1 || sl > 200) return k.setHata("Saatlik sınır 1 ile 200 arasında olmalı.");
    if (!Number.isInteger(gl) || gl < 1 || gl > 1000) return k.setHata("Günlük sınır 1 ile 1000 arasında olmalı.");
    if (!Number.isInteger(b) || b < 0 || b > 23) return k.setHata("Başlangıç saati 0 ile 23 arasında olmalı.");
    if (!Number.isInteger(s) || s < 1 || s > 24) return k.setHata("Bitiş saati 1 ile 24 arasında olmalı.");
    if (b >= s) return k.setHata("Başlangıç saati bitiş saatinden önce olmalı.");
    k.calistir(async () => {
      onKaydet(await ayarlariGuncelle({
        wa_saatlik_limit: sl, wa_gunluk_limit: gl, wa_baslangic_saat: b, wa_bitis_saat: s, wa_push_varsa_atla: atla,
      }));
    });
  }

  return (
    <Kart baslik="WhatsApp gönderimi" aciklama="Hesabın engellenmesini önleyen hız ve saat sınırları">
      <form onSubmit={gonder} noValidate className="space-y-4 max-w-md">
        <div className="grid grid-cols-2 gap-3">
          <label className="block"><span className={etiket}>Saatlik sınır (mesaj)</span>
            <input className={girdi} type="number" min={1} max={200} inputMode="numeric" value={saatlik} onChange={(e) => setSaatlik(e.target.value)} /></label>
          <label className="block"><span className={etiket}>Günlük sınır (mesaj)</span>
            <input className={girdi} type="number" min={1} max={1000} inputMode="numeric" value={gunluk} onChange={(e) => setGunluk(e.target.value)} /></label>
        </div>
        <p className="-mt-2 text-[12px] text-metin-soluk">
          Yeni numarada ilk günlerde otomatik olarak daha düşük bir günlük sınır uygulanır (ısınma); ayardaki değer bunun üstüne çıkamaz.
        </p>
        <fieldset>
          <legend className={etiket}>Gönderim saatleri (İstanbul)</legend>
          <div className="grid grid-cols-2 gap-3">
            <label className="block"><span className="sr-only">Başlangıç saati</span>
              <input className={girdi} type="number" min={0} max={23} inputMode="numeric" aria-label="Başlangıç saati" value={baslangic} onChange={(e) => setBaslangic(e.target.value)} /></label>
            <label className="block"><span className="sr-only">Bitiş saati</span>
              <input className={girdi} type="number" min={1} max={24} inputMode="numeric" aria-label="Bitiş saati" value={bitis} onChange={(e) => setBitis(e.target.value)} /></label>
          </div>
          <p className="mt-1 text-[12px] text-metin-soluk">
            Mesajlar yalnız bu saatler arasında gider (bitiş saati dahil değil); dışındakiler pencere açılınca gönderilir. Örnek: 9 – 21.
          </p>
        </fieldset>
        <label className="flex items-start gap-2 min-h-11 md:min-h-0 text-sm">
          <input type="checkbox" className="mt-1" checked={atla} onChange={(e) => setAtla(e.target.checked)} aria-describedby="wa-atla-ipucu" />
          <span>Uygulama bildirimi alan velilere WhatsApp gönderme</span>
        </label>
        <p id="wa-atla-ipucu" className="-mt-2 text-[12px] text-metin-soluk">
          Son 30 günde uygulama bildirimi ulaşmış velilere ikinci kez WhatsApp gönderilmez; mesaj sayısı ve hesabın engellenme riski azalır. Duyuruda "Her iki kanaldan da gönder" seçilirse bu kural o duyuru için uygulanmaz.
        </p>
        <Sonuc hata={k.hata} tamam={k.tamam} mesaj="WhatsApp gönderim ayarları kaydedildi." />
        <button type="submit" disabled={k.mesgul} className={birincilDugme}>
          {k.mesgul ? "Kaydediliyor…" : "WhatsApp ayarlarını kaydet"}
        </button>
      </form>
    </Kart>
  );
}

export default function WhatsApp() {
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
      <SayfaBasligi baslik="WhatsApp" />
      {hata && <p role="alert" className="text-sm text-hata">{hata}</p>}
      <div className="grid gap-4 lg:grid-cols-2 items-start">
        <WhatsAppBaglantisi />
        {veri && <WhatsAppGonderimKarti veri={veri} onKaydet={setVeri} />}
      </div>
    </>
  );
}
