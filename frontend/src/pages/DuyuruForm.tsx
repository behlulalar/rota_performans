import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  duyuruGonder,
  duyuruOnizle,
  type DuyuruHedefi,
  type HedefTuru,
  type Onizleme,
} from "../api/duyuru";
import { gruplariGetir, type GrupOzet } from "../api/grup";
import { oturumGetir, takvimGetir, type OturumOzet } from "../api/takvim";
import { useOnay } from "../components/OnayPenceresi";
import SayfaBasligi from "../components/SayfaBasligi";
import WhatsAppUyarisi, { useWhatsAppDurumu } from "../components/WhatsAppUyarisi";
import { hataMesaji } from "../lib/dogrulama";
import { saat } from "../lib/program";
import { birincilDugme, girdi, kartKutusu, secimKutusu } from "../lib/stil";
import { gunEkle, kisaTarih, tarihCoz, yyyyAyGun } from "../lib/tarih";

const EN_COK_METIN = 1000;
const EN_COK_BASLIK = 120;
const ONIZLEME_GUN = 14;

type SablonAdi = "ders_iptali" | "saat_degisikligi" | "genel";
const SABLON_ETIKET: Record<SablonAdi, string> = {
  ders_iptali: "Ders iptali",
  saat_degisikligi: "Saat değişikliği",
  genel: "Genel duyuru",
};
const ON_EK = "Rota Performans Akademi: ";

const oturumEtiketi = (o: OturumOzet) =>
  `${kisaTarih(tarihCoz(o.tarih))} ${saat(o.baslangic)}–${saat(o.bitis)} · ${o.grup.ad}${o.durum === "iptal" ? " (iptal)" : ""}`;

/** Hazır şablonun başlık ve metni. Hedef bir oturumsa tarih, saat ve grup metne işlenir. */
function sablonMetni(
  sablon: SablonAdi,
  o: OturumOzet | null,
): { baslik: string; metin: string } {
  const gun = o
    ? tarihCoz(o.tarih).toLocaleDateString("tr-TR", {
        day: "numeric",
        month: "long",
        weekday: "long",
      })
    : "";
  switch (sablon) {
    case "ders_iptali":
      return {
        baslik: "Ders iptali",
        metin: o
          ? `${ON_EK}${o.grup.ad} grubunun ${gun} günü ${saat(o.baslangic)} dersi iptal edilmiştir. Anlayışınız için teşekkür ederiz.`
          : `${ON_EK}Planlanan dersimiz iptal edilmiştir. Anlayışınız için teşekkür ederiz.`,
      };
    case "saat_degisikligi":
      return {
        baslik: "Ders saati değişikliği",
        metin: o
          ? `${ON_EK}${o.grup.ad} grubunun ${gun} günü ${saat(o.baslangic)} olan dersinin saati [yeni saat] olarak değiştirilmiştir.`
          : `${ON_EK}Dersimizin saati [yeni saat] olarak değiştirilmiştir.`,
      };
    default:
      return { baslik: "", metin: ON_EK };
  }
}

const bolumBasligi = "font-display text-[17px] leading-6";

export default function DuyuruForm() {
  const [params] = useSearchParams();
  const onayla = useOnay();
  const git = useNavigate();
  const oturumParam = params.get("oturum");
  const sablonParam = params.get("sablon") as SablonAdi | null;

  const [hedefTur, setHedefTur] = useState<HedefTuru>(
    oturumParam ? "oturum" : "tum",
  );
  const [oturumId, setOturumId] = useState(oturumParam ?? "");
  const [grupIdleri, setGrupIdleri] = useState<string[]>([]);
  const [oturumlar, setOturumlar] = useState<OturumOzet[]>([]);
  const [gruplar, setGruplar] = useState<GrupOzet[]>([]);
  const [sablon, setSablon] = useState<SablonAdi>(
    sablonParam && sablonParam in SABLON_ETIKET ? sablonParam : "genel",
  );
  const [baslik, setBaslik] = useState("");
  const [metin, setMetin] = useState(ON_EK);
  const duzenlendi = useRef(false);
  const [push, setPush] = useState(true);
  const [whatsapp, setWhatsapp] = useState(false);
  const [herIki, setHerIki] = useState(false);
  const wa = useWhatsAppDurumu();
  // WhatsApp seçeneği yalnız numara bağlıyken etkindir; değilse nedeni yazılır.
  const waNedeni =
    wa === null ? "WhatsApp durumu kontrol ediliyor…"
    : wa.durum === "yapilandirilmadi" ? "WhatsApp kurulmadığı için kapalı."
    : wa.durum === "bagli" ? (wa.devre_kesici.acik ? "WhatsApp gönderimi geçici olarak durduruldu (bağlantı sorunu). Sorun giderilince kendiliğinden açılır; detay için Ayarlar'a bakın." : null)
    : wa.durum === "ulasilamiyor" ? "WhatsApp servisine ulaşılamadığı için kapalı."
    : "WhatsApp bağlı olmadığı için kapalı. Ayarlar sayfasından numarayı bağlayın.";
  const waKapali = waNedeni !== null;
  const [onizleme, setOnizleme] = useState<Onizleme | null>(null);
  const [onizlemeHatasi, setOnizlemeHatasi] = useState<string | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);

  // Yaklaşan dersler (14 gün) ve aktif gruplar. Gelen oturum aralık dışındaysa ayrıca eklenir.
  useEffect(() => {
    let iptal = false;
    (async () => {
      try {
        const t = new Date();
        const [liste, g] = await Promise.all([
          takvimGetir(yyyyAyGun(t), yyyyAyGun(gunEkle(t, ONIZLEME_GUN))),
          gruplariGetir(true),
        ]);
        let tum = liste;
        if (oturumParam && !liste.some((o) => o.id === oturumParam)) {
          const o = await oturumGetir(oturumParam).catch(() => null);
          if (o) tum = [o, ...liste];
        }
        if (iptal) return;
        setOturumlar(tum);
        setGruplar(g);
      } catch (e) {
        if (!iptal) setHata(hataMesaji(e));
      }
    })();
    return () => {
      iptal = true;
    };
  }, [oturumParam]);

  const seciliOturum = useMemo(
    () => oturumlar.find((o) => o.id === oturumId) ?? null,
    [oturumlar, oturumId],
  );

  // Şablon ya da seçili ders değişince, metin elle düzenlenmediyse yeniden doldurulur.
  useEffect(() => {
    if (duzenlendi.current) return;
    const s = sablonMetni(sablon, hedefTur === "oturum" ? seciliOturum : null);
    setBaslik(s.baslik);
    setMetin(s.metin);
  }, [sablon, seciliOturum, hedefTur]);

  const hedef: DuyuruHedefi | null = useMemo(() => {
    if (hedefTur === "tum") return { tur: "tum" };
    if (hedefTur === "oturum")
      return oturumId ? { tur: "oturum", oturum_id: oturumId } : null;
    return grupIdleri.length > 0
      ? { tur: "grup", grup_idleri: grupIdleri }
      : null;
  }, [hedefTur, oturumId, grupIdleri]);

  // Canlı önizleme: hedef değişince sunucudan alıcı sayıları alınır.
  useEffect(() => {
    setOnizleme(null);
    setOnizlemeHatasi(null);
    if (!hedef) return;
    let iptal = false;
    duyuruOnizle(hedef, { push, whatsapp })
      .then((v) => !iptal && setOnizleme(v))
      .catch((e) => !iptal && setOnizlemeHatasi(hataMesaji(e)));
    return () => {
      iptal = true;
    };
  }, [hedef, push, whatsapp]);

  const doldurulmamis = /\[[^\]]+\]/.test(metin);
  const hazir = Boolean(
    hedef &&
    (push || whatsapp) &&
    baslik.trim() &&
    metin.trim() &&
    !doldurulmamis &&
    onizleme &&
    ((push && onizleme.push_alacak > 0) || (whatsapp && onizleme.whatsapp_izinli > 0)),
  );

  const sablonSec = (s: SablonAdi) => {
    duzenlendi.current = false;
    setSablon(s);
    const m = sablonMetni(s, hedefTur === "oturum" ? seciliOturum : null);
    setBaslik(m.baslik);
    setMetin(m.metin);
  };

  const gonder = async () => {
    if (!hedef || !onizleme) return;
    const tamam = await onayla({
      baslik: "Duyuruyu gönder",
      mesaj: `"${baslik.trim()}" duyurusu ${[
        push ? `${onizleme.push_alacak} veliye uygulama bildirimi` : null,
        whatsapp ? `${onizleme.whatsapp_izinli} veliye WhatsApp` : null,
      ].filter(Boolean).join(" ve ")} olarak gönderilecek.${
        push && whatsapp && herIki ? " Uygulama bildirimi alan velilere de WhatsApp gidecek." : ""
      } Gönderilen duyuru geri alınamaz.`,
      onayYazisi: "Gönder",
    });
    if (!tamam) return;
    setGonderiliyor(true);
    setHata(null);
    try {
      const d = await duyuruGonder({
        baslik: baslik.trim(),
        metin: metin.trim(),
        hedef,
        kanallar: { push, whatsapp },
        her_iki_kanal: push && whatsapp && herIki,
      });
      git(`/duyurular/${d.id}`);
    } catch (e) {
      setHata(hataMesaji(e));
      setGonderiliyor(false);
    }
  };

  const grupSec = (id: string, secili: boolean) =>
    setGrupIdleri((l) => (secili ? [...l, id] : l.filter((x) => x !== id)));

  return (
    <div className="space-y-5">
      <div>
        <Link
          to="/duyurular"
          className="inline-flex items-center min-h-11 md:min-h-0 text-[13px] text-metin-soluk hover:text-metin"
        >
          ← Duyurular
        </Link>
      </div>
      <SayfaBasligi
        baslik="Yeni duyuru"
        aciklama="Velilerin birincil iletişim kişisine gider; kardeşler tek bildirim alır"
      />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px] items-start">
        <div className="space-y-5 min-w-0">
          <fieldset className={`${kartKutusu} p-5 space-y-3`}>
            <legend className="sr-only">Kime</legend>
            <h2 className={bolumBasligi} aria-hidden="true">
              Kime
            </h2>
            <div className="flex flex-wrap gap-x-5 gap-y-2">
              {(
                [
                  ["oturum", "Ders oturumu"],
                  ["grup", "Gruplar"],
                  ["tum", "Tüm aktif öğrenciler"],
                ] as [HedefTuru, string][]
              ).map(([t, e]) => (
                <label
                  key={t}
                  className="inline-flex items-center gap-2 min-h-11 md:min-h-0 text-sm"
                >
                  <input
                    type="radio"
                    name="hedef"
                    checked={hedefTur === t}
                    onChange={() => setHedefTur(t)}
                  />
                  {e}
                </label>
              ))}
            </div>
            {hedefTur === "oturum" && (
              <label className="block text-[13px]">
                Ders (önümüzdeki {ONIZLEME_GUN} gün)
                <select
                  value={oturumId}
                  onChange={(e) => setOturumId(e.target.value)}
                  className={`${secimKutusu} mt-1 w-full`}
                >
                  <option value="">Ders seçin…</option>
                  {oturumlar.map((o) => (
                    <option key={o.id} value={o.id}>
                      {oturumEtiketi(o)}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {hedefTur === "grup" && (
              <div
                className="grid gap-1 sm:grid-cols-2"
                role="group"
                aria-label="Gruplar"
              >
                {gruplar.length === 0 && (
                  <p className="text-[13px] text-metin-soluk">
                    Aktif grup yok.
                  </p>
                )}
                {gruplar.map((g) => (
                  <label
                    key={g.id}
                    className="inline-flex items-center gap-2 min-h-11 md:min-h-8 text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={grupIdleri.includes(g.id)}
                      onChange={(e) => grupSec(g.id, e.target.checked)}
                    />
                    {g.ad}
                  </label>
                ))}
              </div>
            )}
          </fieldset>

          <section className={`${kartKutusu} p-5 space-y-3`}>
            <h2 className={bolumBasligi}>Mesaj</h2>
            <label className="block text-[13px]">
              Hazır şablon
              <select
                value={sablon}
                onChange={(e) => sablonSec(e.target.value as SablonAdi)}
                className={`${secimKutusu} mt-1 w-full`}
              >
                {Object.entries(SABLON_ETIKET).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-[13px]">
              Başlık
              <input
                value={baslik}
                maxLength={EN_COK_BASLIK}
                className={girdi}
                onChange={(e) => {
                  duzenlendi.current = true;
                  setBaslik(e.target.value);
                }}
              />
            </label>
            <label className="block text-[13px]">
              Mesaj
              <textarea
                value={metin}
                maxLength={EN_COK_METIN}
                rows={8}
                className={`${girdi} py-2 resize-y`}
                onChange={(e) => {
                  duzenlendi.current = true;
                  setMetin(e.target.value);
                }}
              />
              <span className="num text-xs text-metin-soluk">
                {metin.length}/{EN_COK_METIN}
              </span>
            </label>
            {doldurulmamis && (
              <p role="alert" className="text-[13px] text-uyari">
                Mesajdaki köşeli parantezli yerleri (ör. [yeni saat]) doldurun.
              </p>
            )}
          </section>
        </div>

        <aside className="space-y-5 lg:sticky lg:top-20">
          <fieldset className={`${kartKutusu} p-5 space-y-2`}>
            <legend className="sr-only">Kanal</legend>
            <h2 className={bolumBasligi} aria-hidden="true">
              Kanal
            </h2>
            <label className="flex items-center gap-2 min-h-11 md:min-h-0 text-sm">
              <input
                type="checkbox"
                checked={push}
                onChange={(e) => setPush(e.target.checked)}
              />
              Uygulama bildirimi
            </label>
            <label className={`flex items-center gap-2 min-h-11 md:min-h-0 text-sm ${waKapali ? "text-metin-soluk" : ""}`}>
              <input
                type="checkbox"
                checked={whatsapp && !waKapali}
                disabled={waKapali}
                onChange={(e) => setWhatsapp(e.target.checked)}
              />
              WhatsApp
            </label>
            {waNedeni && (
              <p className="text-xs text-metin-soluk" data-testid="whatsapp-nedeni">{waNedeni}</p>
            )}
            {push && whatsapp && !waKapali && (
              <label className="flex items-start gap-2 min-h-11 md:min-h-0 text-sm pl-6">
                <input type="checkbox" className="mt-1" checked={herIki} onChange={(e) => setHerIki(e.target.checked)} />
                <span>Her iki kanaldan da gönder (push alanlara da WhatsApp gider)</span>
              </label>
            )}
            {push && whatsapp && !waKapali && !herIki && (
              <p className="text-xs text-metin-soluk pl-6">
                Seçilmezse, uygulama bildirimi ulaşan velilere WhatsApp gönderilmez; yalnız bildirim alamayanlara gider.
              </p>
            )}
            {whatsapp && !waKapali && <WhatsAppUyarisi b={wa} sinif="!text-xs" />}
          </fieldset>

          <section className={`${kartKutusu} p-5`} aria-live="polite">
            <h2 className={`${bolumBasligi} mb-2`}>Önizleme</h2>
            {!hedef ? (
              <p className="text-[13px] text-metin-soluk">
                Alıcı sayısını görmek için hedef seçin.
              </p>
            ) : onizlemeHatasi ? (
              <p role="alert" className="text-[13px] text-hata">
                {onizlemeHatasi}
              </p>
            ) : !onizleme ? (
              <p className="text-[13px] text-metin-soluk">Hesaplanıyor…</p>
            ) : (
              <p className="text-sm num" data-testid="onizleme">
                {onizleme.alici} veli ({onizleme.ogrenci} öğrenci) · uygulama
                bildirimi alacak: {onizleme.push_alacak} · bildirimi kapalı veya
                cihazı yok: {onizleme.push_yok}
                {whatsapp && <> · WhatsApp alacak: {onizleme.whatsapp_izinli}</>}
              </p>
            )}
            {onizleme && onizleme.push_alacak === 0 && push && (
              <p className="mt-1 text-[13px] text-uyari">
                Uygulama bildirimi alacak veli yok.
              </p>
            )}
            {onizleme && whatsapp && onizleme.whatsapp_izinli === 0 && (
              <p className="mt-1 text-[13px] text-uyari">
                WhatsApp izni olan veli yok.
              </p>
            )}
            {onizleme && whatsapp && push && !herIki && onizleme.whatsapp_izinli > 0 && (
              <p className="mt-1 text-xs text-metin-soluk">
                WhatsApp sayısı izni olan tüm velileri gösterir; uygulama bildirimi ulaşanlara gönderilmeyebilir.
              </p>
            )}
          </section>

          {hata && (
            <p role="alert" className="text-[13px] text-hata">
              {hata}
            </p>
          )}
          <button
            className={`${birincilDugme} w-full`}
            disabled={!hazir || gonderiliyor}
            onClick={() => void gonder()}
          >
            {gonderiliyor ? "Gönderiliyor…" : "Duyuruyu gönder"}
          </button>
        </aside>
      </div>
    </div>
  );
}
