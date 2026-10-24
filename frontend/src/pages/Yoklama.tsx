import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { ApiHata } from "../lib/api";
import { oturumGetir, yoklamaKaydet, type OturumDetay, type YoklamaDurum } from "../api/takvim";
import OgrenciFoto from "../components/OgrenciFoto";
import SayfaBasligi from "../components/SayfaBasligi";
import { basariKutusu, birincilDugme, rozetBasari, rozetNotr, rozetUyari, uyariKutusu } from "../lib/stil";
import { hataMesaji } from "../lib/dogrulama";
import { saat } from "../lib/program";
import { bugun, uzunTarih } from "../lib/tarih";

type Secim = Record<string, YoklamaDurum | null>;

const ERKEN_ACILIS_DK = 15;

// Antrenör için yoklamanın açıldığı an: ders başlangıcından 15 dk önce, kulüp saati (Türkiye, UTC+3).
// Asıl kontrol sunucuda yapılır; bu yalnızca ekranı buna göre gösterir.
function acilisZamani(o: OturumDetay): Date {
  return new Date(new Date(`${o.tarih}T${saat(o.baslangic)}:00+03:00`).getTime() - ERKEN_ACILIS_DK * 60_000);
}

const saatDakika = (d: Date) =>
  d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Istanbul" });

const secimler = (o: OturumDetay): Secim => Object.fromEntries(o.ogrenciler.map((x) => [x.ogrenci_id, x.yoklama]));

function hataYaz(e: unknown): string {
  if (e instanceof ApiHata && e.durum === 403) return "Bu derse erişim yetkiniz yok";
  return hataMesaji(e);
}

export default function Yoklama() {
  const { id } = useParams();
  const { kullanici } = useAuth();
  const [anlik, setAnlik] = useState(() => Date.now());
  const [o, setO] = useState<OturumDetay | null>(null);
  const [secim, setSecim] = useState<Secim>({});
  const [hata, setHata] = useState<string | null>(null);
  const [bilgi, setBilgi] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);

  useEffect(() => {
    if (!id) return;
    let iptal = false;
    oturumGetir(id)
      .then((v) => {
        if (iptal) return;
        setO(v);
        setSecim(secimler(v));
      })
      .catch((e) => !iptal && setHata(hataYaz(e)));
    return () => {
      iptal = true;
    };
  }, [id]);

  // Açılış saatinde ekran kendiliğinden açılsın diye zaman 30 sn'de bir güncellenir.
  useEffect(() => {
    const t = setInterval(() => setAnlik(Date.now()), 30_000);
    return () => clearInterval(t);
  }, []);

  const isaretli = useMemo(() => Object.values(secim).filter((v) => v !== null).length, [secim]);

  if (hata && !o) {
    return (
      <div className="space-y-3">
        <SayfaBasligi baslik="Yoklama" />
        <Link to="/takvim" className="text-[13px] text-metin-soluk hover:text-metin">← Takvim</Link>
        <p role="alert" className="text-hata">{hata}</p>
      </div>
    );
  }
  if (!o) return <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>;

  const toplam = o.ogrenciler.length;
  const gelecek = o.tarih > bugun();
  const iptal = o.durum === "iptal";
  const acilis = acilisZamani(o);
  const erken = kullanici?.rol === "antrenor" && !gelecek && anlik < acilis.getTime();
  const kilit = gelecek || iptal || erken;

  const sec = (ogrenciId: string, d: YoklamaDurum) => {
    setBilgi(null);
    setSecim((s) => ({ ...s, [ogrenciId]: d }));
  };
  const tumuGeldi = () => {
    setBilgi(null);
    setSecim(Object.fromEntries(o.ogrenciler.map((x) => [x.ogrenci_id, "geldi" as const])));
  };

  const kaydet = async () => {
    const kayitlar = Object.entries(secim)
      .filter((e): e is [string, YoklamaDurum] => e[1] !== null)
      .map(([ogrenci_id, durum]) => ({ ogrenci_id, durum }));
    setMesgul(true);
    setHata(null);
    setBilgi(null);
    try {
      const y = await yoklamaKaydet(o.id, kayitlar);
      setO(y);
      setSecim(secimler(y));
      setBilgi("Yoklama kaydedildi");
    } catch (e) {
      setHata(hataYaz(e));
    } finally {
      setMesgul(false);
    }
  };

  const butonSinif = (aktif: boolean, renk: "basari" | "hata") =>
    `min-h-12 rounded-[3px] border-2 px-2 text-base font-semibold transition-colors disabled:opacity-40 ${
      aktif
        ? renk === "basari"
          ? "bg-basari border-basari text-zemin"
          : "bg-hata border-hata text-zemin"
        : "border-cizgi-guclu bg-yuzey text-metin-orta hover:border-metin-soluk"
    }`;

  return (
    <div className="max-w-2xl">
      <div>
        <Link to="/takvim" className="inline-flex items-center min-h-11 md:min-h-0 text-[13px] text-metin-soluk hover:text-metin">← Takvim</Link>
      </div>
      <SayfaBasligi
        baslik={o.grup.ad}
        rozet={
          <>
            {iptal && <span className={rozetNotr}>İptal edildi</span>}
            {o.yoklama_alindi && <span className={rozetBasari}>Yoklama alındı</span>}
          </>
        }
        aciklama={`${uzunTarih(o.tarih)} · ${saat(o.baslangic)}–${saat(o.bitis)}`}
      />

      {gelecek && (
        <p className={`mb-3 ${uyariKutusu}`}>
          Bu ders henüz yapılmadı; yoklama ders gününde alınabilir.
        </p>
      )}
      {erken && (
        <p className={`mb-3 ${uyariKutusu}`}>
          Yoklama {saatDakika(acilis)}'te açılır (ders başlamadan 15 dakika önce).
        </p>
      )}
      {iptal && (
        <p className="mb-3 rounded-[3px] border border-cizgi-guclu text-metin-soluk text-[13px] px-3 py-2">
          Bu ders iptal edildiği için yoklama alınamaz.
        </p>
      )}
      <p className="mb-3 text-xs text-metin-soluk">
        Gelmedi işaretlenen öğrencilere telafi hakkı 1 saat sonra tanımlanır. Bu süre içinde düzeltebilirsiniz.
      </p>
      {bilgi && <p role="status" className={`mb-3 ${basariKutusu}`}>{bilgi}</p>}
      {hata && <p role="alert" className="mb-3 text-[13px] text-hata">{hata}</p>}

      {toplam === 0 ? (
        <p className="rounded-[5px] border border-cizgi bg-yuzey px-4 py-6 text-sm text-metin-soluk text-center">Bu derste öğrenci yok.</p>
      ) : (
        <>
          <button
            className="mb-3 w-full min-h-12 rounded-[3px] border border-basari/60 bg-basari-zemin text-basari font-semibold disabled:opacity-40"
            disabled={kilit || mesgul}
            onClick={tumuGeldi}
          >
            Tümü geldi
          </button>
          <ul className="space-y-2">
            {o.ogrenciler.map((x) => (
              <li key={x.ogrenci_id} className="rounded-[5px] border border-cizgi bg-yuzey p-3" aria-label={`${x.ad} ${x.soyad}`}>
                <div className="flex items-center gap-3">
                  <OgrenciFoto id={x.ogrenci_id} fotoVar={x.foto_var} ad={x.ad} soyad={x.soyad} boyut="kucuk" sinif="size-12 rounded-full" />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{x.ad} {x.soyad}</span>
                      {x.telafi_mi && <span className={rozetUyari}>Telafi</span>}
                    </div>
                    <div className="num text-xs text-metin-soluk">Kalan: {x.bakiye.normal} · Telafi: {x.bakiye.telafi}</div>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3">
                  <button
                    className={butonSinif(secim[x.ogrenci_id] === "geldi", "basari")}
                    aria-pressed={secim[x.ogrenci_id] === "geldi"}
                    disabled={kilit || mesgul}
                    onClick={() => sec(x.ogrenci_id, "geldi")}
                  >
                    Geldi
                  </button>
                  <button
                    className={butonSinif(secim[x.ogrenci_id] === "gelmedi", "hata")}
                    aria-pressed={secim[x.ogrenci_id] === "gelmedi"}
                    disabled={kilit || mesgul}
                    onClick={() => sec(x.ogrenci_id, "gelmedi")}
                  >
                    Gelmedi
                  </button>
                </div>
              </li>
            ))}
          </ul>

          <div className="sticky bottom-[var(--sekme-yuk,0px)] z-10 mt-4 -mx-4 md:-mx-6 bg-yuzey border-t border-cizgi px-4 md:px-6 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
            {isaretli < toplam && isaretli > 0 && !kilit && (
              <p className="mb-2 text-xs text-uyari">
                {toplam - isaretli} öğrenci işaretlenmedi; yalnızca işaretliler kaydedilir.
              </p>
            )}
            <button
              className={`${birincilDugme} w-full min-h-14 text-base`}
              disabled={kilit || mesgul || isaretli === 0}
              onClick={() => void kaydet()}
            >
              {mesgul ? "Kaydediliyor…" : `Yoklamayı kaydet (${isaretli}/${toplam} işaretli)`}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
