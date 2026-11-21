import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { ApiHata } from "../lib/api";
import { ekDersCikar, oturumGetir, oturumIptalEt, oturumIptalGeriAl, telafiGeriAl, yoklamaKaydet, type OturumDetay, type YoklamaDurum } from "../api/takvim";
import { ogrencilerimGetir } from "../api/devam";
import Modal from "../components/Modal";
import OgrenciFoto from "../components/OgrenciFoto";
import { useOnay } from "../components/OnayPenceresi";
import SayfaBasligi from "../components/SayfaBasligi";
import { basariKutusu, bilgiKutusu, birincilDugme, dugme, rozetBasari, rozetBirincil, rozetNotr, rozetUyari, uyariKutusu } from "../lib/stil";
import { hataMesaji } from "../lib/dogrulama";
import { saat } from "../lib/program";
import { mazeretli, SEBEP_ACIKLAMA_MAKS, SEBEP_AD, SEBEPLER, type Sebep } from "../lib/sebep";
import { gosterilenDers } from "../lib/dersHakki";
import { bugun, uzunTarih } from "../lib/tarih";

type Secim = Record<string, YoklamaDurum | null>;

type Sebepler = Record<string, Sebep | null>;
type Aciklamalar = Record<string, string>;

const ERKEN_ACILIS_DK = 15;

// Antrenör için yoklamanın açıldığı an: ders başlangıcından 15 dk önce, kulüp saati (Türkiye, UTC+3).
// Asıl kontrol sunucuda yapılır; bu yalnızca ekranı buna göre gösterir.
function acilisZamani(o: OturumDetay): Date {
  return new Date(new Date(`${o.tarih}T${saat(o.baslangic)}:00+03:00`).getTime() - ERKEN_ACILIS_DK * 60_000);
}

const saatDakika = (d: Date) =>
  d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Istanbul" });

const secimler = (o: OturumDetay): Secim => Object.fromEntries(o.ogrenciler.map((x) => [x.ogrenci_id, x.yoklama]));

const sebepler = (o: OturumDetay): Sebepler => Object.fromEntries(o.ogrenciler.map((x) => [x.ogrenci_id, x.yoklama === "gelmedi" ? x.sebep ?? null : null]));
const aciklamalar = (o: OturumDetay): Aciklamalar => Object.fromEntries(o.ogrenciler.map((x) => [x.ogrenci_id, x.aciklama ?? ""]));

function hataYaz(e: unknown): string {
  if (e instanceof ApiHata && e.durum === 403 && e.message.includes("kilitlendi")) return e.message;
  if (e instanceof ApiHata && e.durum === 403) return "Bu derse erişim yetkiniz yok";
  return hataMesaji(e);
}

type KayitOzeti = { kilitSaati: string | null; geldi: number; gelmedi: number; sebepler: [Sebep, number][]; isaretsiz: number };

export default function Yoklama() {
  const { id } = useParams();
  const { kullanici } = useAuth();
  const onayla = useOnay();
  const [bildirimTeklifi, setBildirimTeklifi] = useState(false);
  const [anlik, setAnlik] = useState(() => Date.now());
  const [o, setO] = useState<OturumDetay | null>(null);
  const [secim, setSecim] = useState<Secim>({});
  const [sebep, setSebep] = useState<Sebepler>({});
  const [aciklama, setAciklama] = useState<Aciklamalar>({});
  const [aciklamaAcik, setAciklamaAcik] = useState<Record<string, boolean>>({});
  const [denendi, setDenendi] = useState(false);
  const [hata, setHata] = useState<string | null>(null);
  const [bilgi, setBilgi] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const [ozet, setOzet] = useState<KayitOzeti | null>(null);
  const gezin = useNavigate();
  // Antrenör yalnız kendi gruplarındaki öğrencinin telafisini kaldırabilir (sunucu 403 verir); liste bir kez yüklenir.
  const [kendiOgrenciler, setKendiOgrenciler] = useState<Set<string> | null>(null);
  const antrenorMu = kullanici?.rol === "antrenor";
  const telafiVar = !!o?.ogrenciler.some((x) => x.telafi_mi || x.ek_ders_mi);
  useEffect(() => {
    if (!antrenorMu || !telafiVar || kendiOgrenciler) return;
    ogrencilerimGetir()
      .then((g) => setKendiOgrenciler(new Set(g.flatMap((x) => x.ogrenciler.map((s) => s.ogrenci_id)))))
      .catch(() => setKendiOgrenciler(new Set()));
  }, [antrenorMu, telafiVar, kendiOgrenciler]);

  useEffect(() => {
    if (!id) return;
    let iptal = false;
    oturumGetir(id)
      .then((v) => {
        if (iptal) return;
        setO(v);
        setSecim(secimler(v));
        setSebep(sebepler(v));
        setAciklama(aciklamalar(v));
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
  const yonetici = kullanici?.rol === "admin" || kullanici?.rol === "destek";
  // Sunucu `kilitli` der ve kullanıcı antrenörse ekran salt okunurdur; yönetici düzeltebilir.
  const antrenorKilitli = !yonetici && o.kilitli;
  const yoneticiKilitli = yonetici && o.kilitli;
  const duzenlemeSaati = o.kilit_zamani ? saatDakika(new Date(o.kilit_zamani)) : null;
  const kilit = gelecek || iptal || erken || antrenorKilitli;

  const sec = (ogrenciId: string, d: YoklamaDurum) => {
    setBilgi(null);
    setSecim((s) => ({ ...s, [ogrenciId]: d }));
    // Geldi'ye dönülürse sebep ve açıklama silinir (sunucu geldi ile birlikte kabul etmez).
    if (d === "geldi") {
      setSebep((s) => ({ ...s, [ogrenciId]: null }));
      setAciklama((s) => ({ ...s, [ogrenciId]: "" }));
      setAciklamaAcik((s) => ({ ...s, [ogrenciId]: false }));
    }
  };
  const sebepsiz = (ogrenciId: string) => secim[ogrenciId] === "gelmedi" && !sebep[ogrenciId];
  const sebepsizSayisi = Object.keys(secim).filter(sebepsiz).length;
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
    if (sebepsizSayisi > 0) {
      setDenendi(true);
      setBilgi(null);
      return;
    }
    const kayitlar = Object.entries(secim)
      .filter((e): e is [string, YoklamaDurum] => e[1] !== null)
      .map(([ogrenci_id, durum]) => {
        if (durum !== "gelmedi") return { ogrenci_id, durum };
        const a = (aciklama[ogrenci_id] ?? "").trim();
        return { ogrenci_id, durum, sebep: sebep[ogrenci_id] ?? undefined, ...(a ? { aciklama: a } : {}) };
      });
    setMesgul(true);
    setHata(null);
    setBilgi(null);
    try {
      const y = await yoklamaKaydet(o.id, kayitlar);
      const gelmediler = kayitlar.filter((k) => k.durum === "gelmedi");
      setOzet({
        kilitSaati: y.kilit_zamani ? saatDakika(new Date(y.kilit_zamani)) : null,
        geldi: kayitlar.filter((k) => k.durum === "geldi").length,
        gelmedi: gelmediler.length,
        sebepler: SEBEPLER.map((b): [Sebep, number] => [b.anahtar, gelmediler.filter((k) => "sebep" in k && k.sebep === b.anahtar).length]).filter(([, n]) => n > 0),
        isaretsiz: o.ogrenciler.length - kayitlar.length,
      });
      setO(y);
      setSecim(secimler(y));
      setSebep(sebepler(y));
      setAciklama(aciklamalar(y));
      setDenendi(false);
    } catch (e) {
      setHata(hataYaz(e));
      // Sayfa açıkken kilit dolduysa ekran salt okunur görünüme geçsin.
      if (e instanceof ApiHata && e.durum === 403 && e.message.includes("kilitlendi")) {
        oturumGetir(o.id).then((y) => { setO(y); setSecim(secimler(y)); setSebep(sebepler(y)); setAciklama(aciklamalar(y)); }).catch(() => {});
      }
    } finally {
      setMesgul(false);
    }
  };

  // Yalnız yönetici iptal edebilir; yoklaması alınmış ya da zaten iptal/yapıldı olan ders iptal edilemez.
  const iptalEdilebilir = yonetici && o.durum === "planli" && !o.yoklama_alindi;
  const geriAlinabilir = yonetici && iptal && o.tarih >= bugun();
  const telafiSayisi = o.ogrenciler.filter((x) => x.telafi_mi).length;

  const telafiKaldir = async (x: OturumDetay["ogrenciler"][number]) => {
    const ek = !!x.ek_ders_mi;
    if (!(await onayla(ek
      ? { baslik: "Ek dersi kaldır", mesaj: `${x.ad} ${x.soyad} bu ek dersten kaldırılsın mı?`, onayYazisi: "Kaldır", tehlikeli: true }
      : { baslik: "Telafiyi kaldır", mesaj: `${x.ad} ${x.soyad} bu telafi dersinden kaldırılsın mı? Telafi hakkı iade edilir.`, onayYazisi: "Kaldır", tehlikeli: true }))) return;
    setMesgul(true);
    setHata(null);
    setBilgi(null);
    try {
      const y = await (ek ? ekDersCikar : telafiGeriAl)(o.id, x.ogrenci_id);
      setO(y);
      const cikar = <T,>(m: Record<string, T>) => Object.fromEntries(Object.entries(m).filter(([k]) => k !== x.ogrenci_id)) as Record<string, T>;
      setSecim(cikar);
      setSebep(cikar);
      setAciklama(cikar);
    } catch (e) {
      setHata(hataYaz(e));
    } finally {
      setMesgul(false);
    }
  };

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
      setSebep(sebepler(y));
      setAciklama(aciklamalar(y));
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

  const chipSinif = (aktif: boolean) =>
    `min-h-11 rounded-[10px] border px-2 text-sm font-medium transition-colors disabled:opacity-40 ${
      aktif ? "border-altin bg-altin/15 text-altin-metin" : "border-cizgi-guclu bg-yuzey text-metin-orta hover:border-metin-soluk"
    }`;

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
      {ozet && (
        <Modal baslik="Yoklama kaydedildi" onKapat={() => setOzet(null)} kolayKapanir>
          <div className="flex items-start gap-3" data-testid="yoklama-ozet">
            <span className="size-9 shrink-0 rounded-full bg-basari-zemin text-basari grid place-items-center" aria-hidden="true">
              <svg viewBox="0 0 16 16" className="size-5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 8.5l3.2 3.2L13 4.5" /></svg>
            </span>
            <ul className="text-sm space-y-1 pt-1.5">
              <li>Geldi: <strong>{ozet.geldi}</strong></li>
              <li>
                Gelmedi: <strong>{ozet.gelmedi}</strong>
                {ozet.sebepler.length > 0 && <span className="text-metin-soluk"> ({ozet.sebepler.map(([s, n]) => `${SEBEP_AD[s]}: ${n}`).join(", ")})</span>}
              </li>
              {ozet.isaretsiz > 0 && <li className="text-uyari">{ozet.isaretsiz} öğrenci işaretlenmedi</li>}
            </ul>
          </div>
          <p className="mt-3 text-[13px] text-metin-soluk">
            {yonetici
              ? "Yönetici olarak yoklamayı daha sonra da düzeltebilirsiniz."
              : ozet.kilitSaati
                ? `Yoklama ${ozet.kilitSaati}'e kadar düzeltilebilir.`
                : "Yoklama 1 saat içinde düzeltilebilir."}
          </p>
          <div className="mt-4 flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
            <button type="button" className={dugme} onClick={() => gezin("/takvim")}>Takvime dön</button>
            <button type="button" className={birincilDugme} autoFocus onClick={() => setOzet(null)}>Tamam</button>
          </div>
        </Modal>
      )}
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
      {antrenorKilitli && (
        <p role="status" data-testid="yoklama-kilitli" className={`mb-3 ${uyariKutusu}`}>
          Yoklama kilitlendi · düzeltme için yöneticiye başvurun
        </p>
      )}
      {!yonetici && !o.kilitli && duzenlemeSaati && !iptal && (
        <p data-testid="yoklama-duzenleme-saati" className="mb-3 text-xs text-metin-soluk">Düzenleme {duzenlemeSaati}'e kadar açık</p>
      )}
      {yoneticiKilitli && (
        <p data-testid="yoklama-yonetici-notu" className="mb-3 text-xs text-metin-soluk">
          Kilit süresi doldu; yönetici olarak düzeltiyorsunuz (denetim kaydına yazılır)
        </p>
      )}
      <p className="mb-3 text-xs text-metin-soluk">
        Gelmedi işaretlenen öğrencilerin ders hakkı 1 saat sonra işlenir; bu süre içinde düzeltebilirsiniz. İzinli, Raporlu ve Yarışma için telafi hakkı doğar, Devamsız için doğmaz.
      </p>
      {bilgi && <p role="status" className={`mb-3 ${basariKutusu}`}>{bilgi}</p>}
      {hata && <p role="alert" className="mb-3 text-[13px] text-hata">{hata}</p>}

      {toplam === 0 ? (
        <p className="rounded-[14px] border border-cizgi bg-yuzey px-4 py-6 text-sm text-metin-soluk text-center">Bu derste öğrenci yok.</p>
      ) : (
        <>
          <button
            className="mb-3 w-full md:w-auto md:min-w-64 min-h-12 px-4 py-2 text-sm leading-snug rounded-[10px] border border-basari/60 bg-basari-zemin text-basari font-semibold disabled:opacity-40"
            disabled={kilit || mesgul || (gelmediSayisi > 0 && geldiYapilacak === 0)}
            onClick={tumuGeldi}
          >
            {gelmediSayisi > 0 ? `Gelmedi dışındakileri geldi işaretle (${geldiYapilacak})` : "Tümü geldi"}
          </button>
          <ul className="grid gap-2 md:grid-cols-2 min-[1360px]:grid-cols-3 items-start">
            {o.ogrenciler.map((x) => (
              <li
                key={x.ogrenci_id}
                className={`rounded-[14px] border bg-yuzey p-3 ${denendi && sebepsiz(x.ogrenci_id) ? "border-hata ring-1 ring-hata" : "border-cizgi"}`}
                data-eksik={denendi && sebepsiz(x.ogrenci_id) ? "true" : undefined}
                aria-label={`${x.ad} ${x.soyad}`}>
                <div className="flex items-center gap-3">
                  <OgrenciFoto id={x.ogrenci_id} fotoVar={x.foto_var} ad={x.ad} soyad={x.soyad} boyut="kucuk" sinif="size-12 rounded-full" />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{x.ad} {x.soyad}</span>
                      {x.telafi_mi && <span className={rozetUyari}>Telafi</span>}
                      {x.ek_ders_mi && <span className={rozetBirincil}>Ek ders</span>}
                      {(x.telafi_mi || x.ek_ders_mi) && x.yoklama === null && o.durum === "planli" && !antrenorKilitli && (yonetici || kendiOgrenciler?.has(x.ogrenci_id)) && (
                        <button className={`${dugme} min-h-11`} disabled={mesgul} aria-label={`${x.ek_ders_mi ? "Ek dersi" : "Telafiyi"} kaldır: ${x.ad} ${x.soyad}`} onClick={() => void telafiKaldir(x)}>Kaldır</button>
                      )}
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
                {secim[x.ogrenci_id] === "gelmedi" && (
                  <div className="mt-3" data-testid="sebep-alani">
                    <div role="group" aria-label="Devamsızlık sebebi" className="grid grid-cols-2 md:grid-cols-4 gap-2">
                      {SEBEPLER.map((b) => (
                        <button
                          key={b.anahtar}
                          type="button"
                          className={chipSinif(sebep[x.ogrenci_id] === b.anahtar)}
                          aria-pressed={sebep[x.ogrenci_id] === b.anahtar}
                          disabled={kilit || mesgul}
                          onClick={() => {
                            setBilgi(null);
                            setSebep((s) => ({ ...s, [x.ogrenci_id]: b.anahtar }));
                          }}
                        >
                          {b.ad}
                        </button>
                      ))}
                    </div>
                    {sebep[x.ogrenci_id] ? (
                      <p className="mt-1.5 text-xs text-metin-soluk">
                        {x.ek_ders_mi ? "Ek ders ücretsizdir, ders hakkını etkilemez" : mazeretli(sebep[x.ogrenci_id] as Sebep) ? "Telafi bu ay içinde planlanmalı" : "Ders hakkı düşer"}
                      </p>
                    ) : (
                      <p className={`mt-1.5 text-xs ${denendi ? "text-hata font-medium" : "text-metin-soluk"}`} role={denendi ? "alert" : undefined}>
                        Devamsızlık sebebi seçin
                      </p>
                    )}
                    {aciklamaAcik[x.ogrenci_id] || aciklama[x.ogrenci_id] ? (
                      <label className="mt-2 block text-xs text-metin-soluk">
                        Açıklama (yalnız antrenör ve yönetici görür)
                        <textarea
                          className="mt-1 w-full rounded-[10px] bg-zemin border border-cizgi-guclu px-3 py-2 text-sm text-metin outline-none focus:border-altin"
                          rows={2}
                          maxLength={SEBEP_ACIKLAMA_MAKS}
                          value={aciklama[x.ogrenci_id] ?? ""}
                          disabled={kilit || mesgul}
                          onChange={(e) => setAciklama((s) => ({ ...s, [x.ogrenci_id]: e.target.value }))}
                        />
                        <span className="num block text-right">{(aciklama[x.ogrenci_id] ?? "").length}/{SEBEP_ACIKLAMA_MAKS}</span>
                      </label>
                    ) : (
                      <button
                        type="button"
                        className="mt-1 min-h-11 text-[13px] font-semibold hover:text-altin-metin disabled:opacity-40"
                        disabled={kilit || mesgul}
                        onClick={() => setAciklamaAcik((s) => ({ ...s, [x.ogrenci_id]: true }))}
                      >
                        + Açıklama ekle
                      </button>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>

          {!antrenorKilitli && (
          <div className="sticky bottom-[var(--sekme-yuk,0px)] z-10 mt-4 -mx-4 md:-mx-8 bg-yuzey border-t border-cizgi px-4 md:px-8 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
            {denendi && sebepsizSayisi > 0 && (
              <p role="alert" className="mb-2 text-[13px] font-medium text-hata">
                Kaydedilemedi: {sebepsizSayisi} gelmedi öğrenci için devamsızlık sebebi seçilmeli.
              </p>
            )}
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
          )}
        </>
      )}
    </div>
  );
}
