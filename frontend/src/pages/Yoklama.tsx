import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { ApiHata } from "../lib/api";
import { oturumGetir, oturumIptalEt, oturumIptalGeriAl, yoklamaKaydet, type OturumDetay, type YoklamaDurum } from "../api/takvim";
import OgrenciFoto from "../components/OgrenciFoto";
import { useOnay } from "../components/OnayPenceresi";
import SayfaBasligi from "../components/SayfaBasligi";
import { basariKutusu, bilgiKutusu, birincilDugme, dugme, rozetBasari, rozetNotr, rozetUyari, uyariKutusu } from "../lib/stil";
import { hataMesaji } from "../lib/dogrulama";
import { saat } from "../lib/program";
import { gosterilenDers } from "../lib/dersHakki";
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
  const onayla = useOnay();
  const [bildirimTeklifi, setBildirimTeklifi] = useState(false);
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
  // Gelmedi işaretlenmiş öğrencilere dokunulmaz; yalnızca geri kalanlar geldi olur.
  const gelmediSayisi = Object.values(secim).filter((v) => v === "gelmedi").length;
  const geldiYapilacak = o.ogrenciler.filter((x) => secim[x.ogrenci_id] !== "gelmedi" && secim[x.ogrenci_id] !== "geldi").length;
  const tumuGeldi = () => {
    setBilgi(null);
    setSecim((s) => ({
      ...s,
      ...Object.fromEntries(o.ogrenciler.filter((x) => s[x.ogrenci_id] !== "gelmedi").map((x) => [x.ogrenci_id, "geldi" as const])),
    }));
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

  // Yalnız yönetici iptal edebilir; yoklaması alınmış ya da zaten iptal/yapıldı olan ders iptal edilemez.
  const yonetici = kullanici?.rol === "admin" || kullanici?.rol === "destek";
  const iptalEdilebilir = yonetici && o.durum === "planli" && !o.yoklama_alindi;
  const geriAlinabilir = yonetici && iptal && o.tarih >= bugun();
  const telafiSayisi = o.ogrenciler.filter((x) => x.telafi_mi).length;

  const dersiIptalEt = async () => {
    const tamam = await onayla({
      baslik: "Dersi iptal et",
      mesaj: `${o.grup.ad} grubunun ${uzunTarih(o.tarih)} ${saat(o.baslangic)} dersi iptal edilecek.${
        telafiSayisi > 0 ? ` Bu derse eklenen ${telafiSayisi} telafi planı silinir; öğrencilerin telafi hakkı yeniden planlanabilir olur.` : ""
      }`,
      onayYazisi: "Dersi iptal et",
      tehlikeli: true,
    });
    if (!tamam) return;
    setMesgul(true);
    setHata(null);
    setBilgi(null);
    try {
      const y = await oturumIptalEt(o.id);
      setO(y);
      setSecim(secimler(y));
      setBildirimTeklifi(true);
    } catch (e) {
      setHata(hataYaz(e));
    } finally {
      setMesgul(false);
    }
  };

  const iptaliGeriAl = async () => {
    const tamam = await onayla({
      baslik: "İptali geri al",
      mesaj: "Ders yeniden planlı olacak. Silinen telafi planları geri gelmez. Daha önce gönderilen duyurular geri alınmaz.",
      onayYazisi: "Geri al",
    });
    if (!tamam) return;
    setMesgul(true);
    setHata(null);
    try {
      const y = await oturumIptalGeriAl(o.id);
      setO(y);
      setSecim(secimler(y));
      setBildirimTeklifi(false);
      setBilgi("Dersin iptali geri alındı");
    } catch (e) {
      setHata(hataYaz(e));
    } finally {
      setMesgul(false);
    }
  };

  const butonSinif = (aktif: boolean, renk: "basari" | "hata") =>
    `min-h-12 rounded-[10px] border-2 px-2 text-base font-semibold transition-colors disabled:opacity-40 ${
      aktif
        ? renk === "basari"
          ? "bg-basari border-basari text-zemin"
          : "bg-hata border-hata text-zemin"
        : "border-cizgi-guclu bg-yuzey text-metin-orta hover:border-metin-soluk"
    }`;

  return (
    <div>
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
        eylemler={
          iptalEdilebilir ? (
            <button className={`${dugme} !border-hata/60 !text-hata`} disabled={mesgul} onClick={() => void dersiIptalEt()}>
              Dersi iptal et
            </button>
          ) : undefined
        }
      />
      {bildirimTeklifi && iptal && (
        <div role="status" className={`mb-3 ${bilgiKutusu} flex flex-wrap items-center justify-between gap-3`} data-testid="bildirim-teklifi">
          <span>Ders iptal edildi. Velilere bildirilsin mi?</span>
          <span className="flex gap-2">
            <Link to={`/duyurular/yeni?oturum=${o.id}&sablon=ders_iptali`} className={dugme}>Velilere bildir</Link>
            <button className={dugme} onClick={() => setBildirimTeklifi(false)}>Şimdi değil</button>
          </span>
        </div>
      )}

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
        <p className="mb-3 rounded-[10px] border border-cizgi-guclu text-metin-soluk text-[13px] px-3 py-2">
          Bu ders iptal edildiği için yoklama alınamaz.
          {yonetici && (
            <span className="mt-2 flex flex-wrap gap-2">
              <Link to={`/duyurular/yeni?oturum=${o.id}&sablon=ders_iptali`} className={dugme}>Velilere duyuru gönder</Link>
              {geriAlinabilir && <button className={dugme} disabled={mesgul} onClick={() => void iptaliGeriAl()}>İptali geri al</button>}
            </span>
          )}
        </p>
      )}
      <p className="mb-3 text-xs text-metin-soluk">
        Gelmedi işaretlenen öğrencilere telafi hakkı 1 saat sonra tanımlanır. Bu süre içinde düzeltebilirsiniz.
      </p>
      {bilgi && <p role="status" className={`mb-3 ${basariKutusu}`}>{bilgi}</p>}
      {hata && <p role="alert" className="mb-3 text-[13px] text-hata">{hata}</p>}

      {toplam === 0 ? (
        <p className="rounded-[14px] border border-cizgi bg-yuzey px-4 py-6 text-sm text-metin-soluk text-center">Bu derste öğrenci yok.</p>
      ) : (
        <>
          <button
            className="mb-3 w-full md:w-auto md:min-w-64 min-h-12 rounded-[10px] border border-basari/60 bg-basari-zemin text-basari font-semibold disabled:opacity-40"
            disabled={kilit || mesgul || (gelmediSayisi > 0 && geldiYapilacak === 0)}
            onClick={tumuGeldi}
          >
            {gelmediSayisi > 0 ? `Gelmedi dışındakileri geldi işaretle (${geldiYapilacak})` : "Tümü geldi"}
          </button>
          <ul className="grid gap-2 md:grid-cols-2 min-[1360px]:grid-cols-3 items-start">
            {o.ogrenciler.map((x) => (
              <li key={x.ogrenci_id} className="rounded-[14px] border border-cizgi bg-yuzey p-3" aria-label={`${x.ad} ${x.soyad}`}>
                <div className="flex items-center gap-3">
                  <OgrenciFoto id={x.ogrenci_id} fotoVar={x.foto_var} ad={x.ad} soyad={x.soyad} boyut="kucuk" sinif="size-12 rounded-full" />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{x.ad} {x.soyad}</span>
                      {x.telafi_mi && <span className={rozetUyari}>Telafi</span>}
                    </div>
                    <div className="num text-xs text-metin-soluk">Kalan: {gosterilenDers(x.bakiye.normal)} · Telafi: {gosterilenDers(x.bakiye.telafi)}</div>
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

          <div className="sticky bottom-[var(--sekme-yuk,0px)] z-10 mt-4 -mx-4 md:-mx-8 bg-yuzey border-t border-cizgi px-4 md:px-8 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
            {isaretli < toplam && isaretli > 0 && !kilit && (
              <p className="mb-2 text-xs text-uyari">
                {toplam - isaretli} öğrenci işaretlenmedi; yalnızca işaretliler kaydedilir.
              </p>
            )}
            <button
              className={`${birincilDugme} w-full md:w-auto md:min-w-96 md:block md:ml-auto min-h-14 text-base`}
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
