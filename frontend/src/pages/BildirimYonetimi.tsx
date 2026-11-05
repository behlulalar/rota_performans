import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  bildirimIptalEt, bildirimleriGetir, bildirimOzetiGetir, bildirimYenidenDene,
  DURUM_ETIKET, SABLON_ETIKET,
  type BildirimDurumu, type BildirimKanali, type BildirimKaydi, type BildirimListesi, type BildirimOzeti,
} from "../api/bildirimYonetimi";
import { useOnay } from "../components/OnayPenceresi";
import WhatsAppUyarisi, { useWhatsAppDurumu } from "../components/WhatsAppUyarisi";
import OzetKarti from "../components/OzetKarti";
import SayfaBasligi from "../components/SayfaBasligi";
import { hataMesaji } from "../lib/dogrulama";
import { dugme, rozetBasari, rozetHata, rozetNotr, rozetUyari, satir, secimKutusu, td, th } from "../lib/stil";

const BOYUT = 20;
const DURUM_ROZET: Record<BildirimDurumu, string> = {
  bekliyor: rozetUyari, gonderildi: rozetBasari, hata: rozetHata, iptal: rozetNotr,
};

const zaman = (iso: string) =>
  new Date(iso).toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });

export default function BildirimYonetimi() {
  const onayla = useOnay();
  const [ozet, setOzet] = useState<BildirimOzeti | null>(null);
  const [durum, setDurum] = useState("");
  const [kanal, setKanal] = useState<BildirimKanali>("push");
  const [sablon, setSablon] = useState("");
  const [arama, setArama] = useState("");
  const [q, setQ] = useState("");
  const [sayfa, setSayfa] = useState(1);
  const [veri, setVeri] = useState<BildirimListesi | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<string | null>(null);
  const [islemHatasi, setIslemHatasi] = useState<string | null>(null);
  const [surum, setSurum] = useState(0);
  const wa = useWhatsAppDurumu();

  useEffect(() => {
    const t = setTimeout(() => { setQ(arama.trim()); setSayfa(1); }, 300);
    return () => clearTimeout(t);
  }, [arama]);

  useEffect(() => {
    let iptal = false;
    bildirimOzetiGetir(kanal).then((v) => !iptal && setOzet(v)).catch(() => undefined);
    return () => { iptal = true; };
  }, [surum, kanal]);

  useEffect(() => {
    let iptal = false;
    setYukleniyor(true);
    setHata(null);
    bildirimleriGetir({ durum, kanal, sablon, q, sayfa, boyut: BOYUT })
      .then((v) => !iptal && setVeri(v))
      .catch((e) => !iptal && setHata(hataMesaji(e)))
      .finally(() => !iptal && setYukleniyor(false));
    return () => { iptal = true; };
  }, [durum, kanal, sablon, q, sayfa, surum]);

  const islem = async (b: BildirimKaydi, tur: "iptal" | "yeniden") => {
    const ad = `${b.ogrenci.ad} ${b.ogrenci.soyad}`;
    const tamam = await onayla(
      tur === "iptal"
        ? { baslik: "Bildirimi iptal et", mesaj: `${ad} için bekleyen bildirim gönderilmeyecek.`, onayYazisi: "İptal et", tehlikeli: true }
        : { baslik: "Yeniden dene", mesaj: `${ad} için bildirim yeniden kuyruğa alınacak.`, onayYazisi: "Yeniden dene" },
    );
    if (!tamam) return;
    setIslemHatasi(null);
    try {
      await (tur === "iptal" ? bildirimIptalEt(b.id) : bildirimYenidenDene(b.id));
      setSurum((s) => s + 1);
    } catch (e) {
      setIslemHatasi(hataMesaji(e));
    }
  };

  const eylem = (b: BildirimKaydi) => (
    <>
      {b.durum === "bekliyor" && (
        <button className={dugme} aria-label={`${b.ogrenci.ad} ${b.ogrenci.soyad} bildirimini iptal et`} onClick={() => islem(b, "iptal")}>İptal</button>
      )}
      {b.durum === "hata" && (
        <button className={dugme} aria-label={`${b.ogrenci.ad} ${b.ogrenci.soyad} bildirimini yeniden dene`} onClick={() => islem(b, "yeniden")}>Yeniden dene</button>
      )}
    </>
  );
  const rozet = (b: BildirimKaydi) => <span className={DURUM_ROZET[b.durum]}>{DURUM_ETIKET[b.durum]}</span>;
  const hataNotu = (b: BildirimKaydi) => b.hata ? <div className="text-xs text-hata mt-0.5">Hata: {b.hata}{b.deneme > 0 && ` (${b.deneme}. deneme)`}</div> : null;
  const ogrenciBaglantisi = (b: BildirimKaydi) => (
    <Link to={`/ogrenciler/${b.ogrenci.id}`} className="font-medium hover:text-altin-metin">{b.ogrenci.ad} {b.ogrenci.soyad}</Link>
  );

  const sayfaSayisi = veri ? Math.max(1, Math.ceil(veri.toplam / veri.boyut)) : 1;
  const s7 = ozet?.son_7_gun;

  return (
    <div className="space-y-6">
      <SayfaBasligi baslik="Bildirimler" aciklama="Velilere giden bildirimlerin kuyruğu ve gönderim durumu" />

      <div role="tablist" aria-label="Kanal" className="flex gap-1 border-b border-cizgi">
        {([["push", "Uygulama bildirimleri"], ["whatsapp", "WhatsApp"]] as [BildirimKanali, string][]).map(([k, e]) => (
          <button
            key={k} role="tab" aria-selected={kanal === k} type="button"
            onClick={() => { setKanal(k); setSayfa(1); setOzet(null); }}
            className={`px-4 min-h-11 text-[13px] font-medium border-b-2 -mb-px transition-colors ${
              kanal === k ? "border-altin text-altin-metin" : "border-transparent text-metin-soluk hover:text-metin"
            }`}
          >
            {e}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" data-testid="bildirim-ozet">
        <OzetKarti etiket="Bekliyor" deger={s7 ? s7.bekliyor : "—"} ton="uyari" ipucu={ozet && ozet.geciken_bekleyen > 0 ? `${ozet.geciken_bekleyen} tanesi gecikmiş` : "Son 7 gün"} />
        <OzetKarti etiket="Gönderildi" deger={s7 ? s7.gonderildi : "—"} ipucu="Son 7 gün" />
        <OzetKarti etiket="Hatalı" deger={s7 ? s7.hata : "—"} ipucu="Son 7 gün" />
        <OzetKarti etiket="İptal" deger={s7 ? s7.iptal : "—"} ipucu="Son 7 gün" />
      </div>

      <div className="text-[13px] space-y-1">
        {kanal === "push" && ozet && (
          <p data-testid="push-durumu">
            Uygulama bildirimleri: <span className={ozet.push_etkin ? "text-basari font-medium" : "text-uyari font-medium"}>{ozet.push_etkin ? "etkin" : "kapalı (VAPID anahtarı girilmemiş)"}</span>
            {" · "}<span className="num">{ozet.push_cihaz_sayisi}</span> cihaz kayıtlı
            {ozet.push_cihaz_sayisi > 0 && <> (<span className="num">{ozet.push_kullanici_sayisi}</span> kullanıcı)</>}
          </p>
        )}
        {kanal === "whatsapp" && (
          <>
            {wa?.durum === "yapilandirilmadi" && (
              <p className="text-metin-soluk" data-testid="wa-kurulmadi">WhatsApp henüz kurulmadı; kurulum ve bağlantı Ayarlar sayfasındadır.</p>
            )}
            {wa && wa.durum !== "yapilandirilmadi" && (
              <p data-testid="wa-durumu">
                WhatsApp: <span className={wa.durum === "bagli" && !wa.devre_kesici.acik ? "text-basari font-medium" : "text-uyari font-medium"}>
                  {wa.devre_kesici.acik ? "gönderim durduruldu" : wa.durum === "bagli" ? "bağlı" : "bağlı değil"}
                </span>
                {" · "}kuyrukta bekleyen: <span className="num">{wa.bekleyen_sayisi}</span>
                {" · "}<Link to="/ayarlar" className="text-altin-metin hover:underline">Ayarlar</Link>
              </p>
            )}
            <WhatsAppUyarisi b={wa} sinif="mt-2" />
          </>
        )}
      </div>

      <div className="flex flex-wrap gap-3">
        <select value={durum} onChange={(e) => { setDurum(e.target.value); setSayfa(1); }} aria-label="Durum filtresi" className={secimKutusu}>
          <option value="">Tüm durumlar</option>
          {Object.entries(DURUM_ETIKET).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select value={sablon} onChange={(e) => { setSablon(e.target.value); setSayfa(1); }} aria-label="Tür filtresi" className={secimKutusu}>
          <option value="">Tüm türler</option>
          {Object.entries(SABLON_ETIKET).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input type="search" value={arama} onChange={(e) => setArama(e.target.value)} placeholder="Öğrenci ara…" aria-label="Öğrenci ara" className={`${secimKutusu} flex-1 min-w-48 max-w-sm`} />
      </div>

      {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
      {islemHatasi && <p role="alert" className="text-[13px] text-hata">{islemHatasi}</p>}
      {!veri ? (
        !hata && <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>
      ) : veri.kayitlar.length === 0 ? (
        <div className="bg-yuzey border border-cizgi rounded-[14px] p-10 text-center text-metin-soluk">Bu filtrede bildirim yok.</div>
      ) : (
        <div className={yukleniyor ? "opacity-60" : ""}>
          <div className="hidden md:block bg-yuzey border border-cizgi rounded-[14px] overflow-hidden">
            <table className="w-full text-[13px]" aria-label="Bildirimler">
              <thead><tr>
                <th className={th}>Zaman</th><th className={th}>Öğrenci</th><th className={th}>Tür</th><th className={th}>Mesaj</th><th className={th}>Durum</th><th className={th}></th>
              </tr></thead>
              <tbody>
                {veri.kayitlar.map((b) => (
                  <tr key={b.id} className={`${satir} align-top`}>
                    <td className={`${td} num py-2 whitespace-nowrap`}>{zaman(b.olusturma)}</td>
                    <td className={`${td} py-2`}>{ogrenciBaglantisi(b)}<div className="text-xs text-metin-soluk">{b.alici.ad_soyad}</div></td>
                    <td className={`${td} py-2`}>{SABLON_ETIKET[b.sablon] ?? b.sablon_etiket}</td>
                    
                    <td className={`${td} py-2 max-w-md text-metin-orta`}>{b.metin}</td>
                    <td className={`${td} py-2`}>{rozet(b)}{hataNotu(b)}</td>
                    <td className={`${td} py-2 text-right`}>{eylem(b)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="md:hidden space-y-2">
            {veri.kayitlar.map((b) => (
              <li key={b.id} className="bg-yuzey border border-cizgi rounded-[14px] p-4 space-y-1.5">
                <div className="flex items-start justify-between gap-2">{ogrenciBaglantisi(b)}{rozet(b)}</div>
                <div className="text-xs text-metin-soluk num">{zaman(b.olusturma)} · {SABLON_ETIKET[b.sablon] ?? b.sablon_etiket}</div>
                <p className="text-[13px] text-metin-orta">{b.metin}</p>
                {hataNotu(b)}
                <div>{eylem(b)}</div>
              </li>
            ))}
          </ul>
          <div className="flex items-center justify-between gap-3 mt-4 text-[13px]">
            <span className="text-metin-soluk num">{veri.toplam} kayıt · Sayfa {veri.sayfa} / {sayfaSayisi}</span>
            <div className="flex gap-2">
              <button className={dugme} disabled={sayfa <= 1} onClick={() => setSayfa((s) => s - 1)}>Önceki</button>
              <button className={dugme} disabled={sayfa >= sayfaSayisi} onClick={() => setSayfa((s) => s + 1)}>Sonraki</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
