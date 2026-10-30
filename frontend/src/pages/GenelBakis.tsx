import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { resitUyarilariniGetir, type ResitUyarisi } from "../api/ogrenci";
import { genelBakisiGetir, type GenelBakisVerisi } from "../api/genelBakis";
import { takvimGetir, type OturumOzet } from "../api/takvim";
import Kart from "../components/Kart";
import OzetKarti from "../components/OzetKarti";
import SayfaBasligi from "../components/SayfaBasligi";
import DolulukCubugu from "../components/DolulukCubugu";
import OgrenciFoto from "../components/OgrenciFoto";
import ResitGecisi from "../components/ResitGecisi";
import { hataMesaji } from "../lib/dogrulama";
import { paraBicimle } from "../lib/para";
import { programOzeti, saat } from "../lib/program";
import { bilgiKutusu, birincilDugme, dugme, listeSatiri, rozetBasari, rozetNotr, rozetUyari, uyariKutusu } from "../lib/stil";
import { bugun } from "../lib/tarih";

const ROL_ADI: Record<string, string> = { anne: "Anne", baba: "Baba", diger: "Diğer", kendisi: "Kendisi" };
const PARA = new Intl.NumberFormat("tr-TR", { style: "currency", currency: "TRY" });
const TARIH = new Intl.DateTimeFormat("tr-TR");

const simdiSaat = () => {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

function Iskelet({ sinif = "" }: { sinif?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded-[10px] bg-yuzey-yuksek ${sinif}`} />;
}

function KartIskeleti({ satir = 3 }: { satir?: number }) {
  return (
    <div className="bg-yuzey border border-cizgi rounded-[14px] p-6 space-y-4">
      <Iskelet sinif="h-5 w-40" />
      {Array.from({ length: satir }, (_, i) => (
        <Iskelet key={i} sinif="h-9 w-full" />
      ))}
    </div>
  );
}

function Yukleniyor() {
  return (
    <div role="status" aria-label="Yükleniyor" className="space-y-4">
      <Iskelet sinif="h-24 w-full" />
      <div className="grid gap-4 grid-cols-2 md:grid-cols-3 xl:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => (
          <Iskelet key={i} sinif="h-[110px]" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <KartIskeleti />
        <KartIskeleti />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <KartIskeleti satir={2} />
        <KartIskeleti satir={2} />
        <KartIskeleti satir={2} />
      </div>
    </div>
  );
}

type ResitDurumu = { liste: ResitUyarisi[] | null; hata: string | null; yenile: () => Promise<void> };

function ResitKarti({ liste, hata, yenile }: ResitDurumu) {
  const [secili, setSecili] = useState<ResitUyarisi | null>(null);
  const [bilgi, setBilgi] = useState<string | null>(null);

  return (
    <div id="resit-gecisleri" className="scroll-mt-20">
      <Kart baslik="Reşit olan öğrenciler" aciklama="18 yaşını dolduranlar için hesap geçişi" bosluksuz>
        <div className="px-6 pb-4">
          {bilgi && <p role="status" className={bilgiKutusu}>{bilgi}</p>}
          {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
          {!hata && liste === null && <Iskelet sinif="h-12 w-full" />}
          {liste && liste.length === 0 && <p className="text-sm text-metin-soluk">Bekleyen reşit geçişi yok</p>}
        </div>
        {liste && liste.length > 0 && (
          <ul className="border-t border-cizgi">
            {liste.map((o) => (
              <li key={o.id} className={`${listeSatiri} flex flex-wrap items-center justify-between gap-2 px-6 py-2 text-sm`}>
                <div className="min-w-0">
                  <Link to={`/ogrenciler/${o.id}`} className="font-medium hover:text-altin-metin">{o.ad} {o.soyad}</Link>
                  <div className="num text-xs text-metin-soluk">
                    {o.yas} yaş • Birincil: {o.birincil_rol ? (ROL_ADI[o.birincil_rol] ?? o.birincil_rol) : "—"} • Veli hesabı: {o.veli_hesabi_var ? "var" : "yok"}
                  </div>
                </div>
                <button className={dugme} onClick={() => { setBilgi(null); setSecili(o); }}>
                  Geçiş yap
                </button>
              </li>
            ))}
          </ul>
        )}
        {secili && (
          <ResitGecisi
            ogrenci={secili}
            onKapat={() => setSecili(null)}
            onTamam={() => {
              setBilgi(`${secili.ad} ${secili.soyad} için reşit geçişi yapıldı. Şimdi öğrenciye kendi panel hesabını açabilirsiniz.`);
              setSecili(null);
              void yenile();
            }}
          />
        )}
      </Kart>
    </div>
  );
}

type Is = { anahtar: string; ad: string; sayi: number; yol: string; hedef?: string };

function BugunYapilacaklar({ isler }: { isler: Is[] }) {
  const gorunen = isler.filter((i) => i.sayi > 0);
  return (
    <Kart baslik="Bugün yapılacaklar" vurgulu sinif="mb-4">
      {gorunen.length === 0 ? (
        <p className="text-sm text-metin-soluk">Bugün bekleyen iş yok</p>
      ) : (
        <ul className="flex flex-wrap gap-2">
          {gorunen.map((i) => (
            <li key={i.anahtar}>
              <Link
                to={i.yol}
                onClick={(e) => {
                  if (!i.hedef) return;
                  const el = document.getElementById(i.hedef);
                  if (el) {
                    e.preventDefault();
                    el.scrollIntoView({ behavior: "smooth", block: "start" });
                  }
                }}
                className="inline-flex items-center gap-2.5 min-h-11 rounded-[10px] border border-cizgi-guclu bg-yuzey-yuksek px-3 text-[13px] hover:border-altin transition-colors"
              >
                <span className="num rounded-full bg-uyari-zemin text-uyari px-2 py-0.5 text-xs font-semibold leading-4">{i.sayi}</span>
                {i.ad}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Kart>
  );
}

function DersSatiri({ o, kontenjan, simdi }: { o: OturumOzet; kontenjan?: number; simdi: string }) {
  const iptal = o.durum === "iptal";
  const basladi = saat(o.baslangic) <= simdi;
  const alt = [
    saat(o.baslangic),
    o.antrenor?.ad_soyad ?? "Antrenör yok",
    kontenjan !== undefined ? `${o.ogrenci_sayisi}/${kontenjan}` : `${o.ogrenci_sayisi} öğrenci`,
  ].join(" · ");
  return (
    <li className={`${listeSatiri} flex items-center justify-between gap-3 px-6 py-2`}>
      <div className="min-w-0">
        <Link to={`/oturum/${o.id}`} className={`text-sm font-medium hover:text-altin-metin ${iptal ? "line-through opacity-60" : ""}`}>
          {o.grup.ad}
        </Link>
        <div className="num text-xs text-metin-soluk truncate">{alt}</div>
      </div>
      {iptal ? (
        <span className={rozetNotr}>İptal</span>
      ) : o.yoklama_alindi ? (
        <span className={rozetBasari}>Alındı</span>
      ) : basladi ? (
        <span className={rozetUyari}>Bekliyor</span>
      ) : (
        <span className={`${rozetNotr} num`}>{saat(o.baslangic)}'de açılır</span>
      )}
    </li>
  );
}

export default function GenelBakis() {
  const [veri, setVeri] = useState<GenelBakisVerisi | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [dersler, setDersler] = useState<OturumOzet[] | null>(null);
  const [dersHata, setDersHata] = useState<string | null>(null);
  const [resit, setResit] = useState<ResitUyarisi[] | null>(null);
  const [resitHata, setResitHata] = useState<string | null>(null);
  const [simdi, setSimdi] = useState(simdiSaat);

  useEffect(() => {
    const t = setInterval(() => setSimdi(simdiSaat()), 60_000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    let iptal = false;
    genelBakisiGetir()
      .then((v) => { if (!iptal) setVeri(v); })
      .catch((e) => { if (!iptal) setHata(hataMesaji(e)); });
    const b = bugun();
    takvimGetir(b, b)
      .then((v) => { if (!iptal) setDersler(v); })
      .catch((e) => { if (!iptal) setDersHata(hataMesaji(e)); });
    return () => { iptal = true; };
  }, []);

  const resitYukle = useCallback(async () => {
    try {
      setResit(await resitUyarilariniGetir());
      setResitHata(null);
    } catch (e) {
      setResitHata(hataMesaji(e));
    }
  }, []);
  useEffect(() => {
    void resitYukle();
  }, [resitYukle]);

  const bugunDersler = useMemo(
    () => (dersler ?? []).filter((d) => d.durum !== "iptal").sort((a, b) => a.baslangic.localeCompare(b.baslangic)),
    [dersler],
  );
  const tumDersler = useMemo(
    () => [...(dersler ?? [])].sort((a, b) => a.baslangic.localeCompare(b.baslangic)),
    [dersler],
  );
  const bekleyenYoklama = bugunDersler.filter((d) => !d.yoklama_alindi && saat(d.baslangic) <= simdi).length;
  const kontenjanlar = useMemo(
    () => new Map((veri?.gruplar.doluluk_listesi ?? []).map((g) => [g.id, g.kontenjan])),
    [veri],
  );

  const hazir = veri !== null && (dersler !== null || dersHata !== null) && (resit !== null || resitHata !== null);

  const aciklama = veri
    ? `${veri.ogrenci.aktif} aktif öğrenci (${veri.ogrenci.pasif} pasif) · ${veri.gruplar.aktif_grup} grup${
        dersler ? ` · bugün ${bugunDersler.length} ders` : ""
      }`
    : undefined;

  return (
    <div>
      <SayfaBasligi
        bolum="Yönetim"
        baslik="Genel Bakış"
        aciklama={aciklama}
        eylemler={
          <>
            <Link to="/takvim" className={dugme}>Takvimi aç</Link>
            <Link to="/ogrenciler/yeni" className={birincilDugme}>Yeni öğrenci</Link>
          </>
        }
      />

      {hata && <p role="alert" className={`mb-4 ${uyariKutusu}`}>{hata}</p>}
      {!hata && !hazir && <Yukleniyor />}

      {veri && hazir && (
        <>
          <BugunYapilacaklar
            isler={[
              { anahtar: "yoklama", ad: "Yoklaması bekleyen ders", sayi: bekleyenYoklama, yol: "/takvim" },
              { anahtar: "hesapsiz", ad: "Hesabı olmayan öğrenci", sayi: veri.hesapsiz_aktif_ogrenci, yol: "/ogrenciler" },
              { anahtar: "grupsuz", ad: "Gruba kayıtsız öğrenci", sayi: veri.grupsuz_aktif_ogrenci, yol: "/ogrenciler" },
              { anahtar: "resit", ad: "Reşit geçişi", sayi: resit?.length ?? 0, yol: "/genel-bakis", hedef: "resit-gecisleri" },
            ]}
          />

          <Ozet v={veri} bugunSayi={dersler ? bugunDersler.length : null} bugunOgrenci={bugunDersler.reduce((t, d) => t + d.ogrenci_sayisi, 0)} />

          <div className="grid gap-4 lg:grid-cols-2 items-start mb-4">
            <Kart baslik="Bugünün dersleri" aciklama="Takvimdeki bugünkü oturumlar" bosluksuz>
              {dersHata ? (
                <p role="alert" className="px-6 pb-6 text-[13px] text-hata">{dersHata}</p>
              ) : tumDersler.length === 0 ? (
                <p className="px-6 pb-6 text-sm text-metin-soluk">Bugün ders yok</p>
              ) : (
                <ul className="border-t border-cizgi">
                  {tumDersler.map((o) => (
                    <DersSatiri key={o.id} o={o} kontenjan={kontenjanlar.get(o.grup.id)} simdi={simdi} />
                  ))}
                </ul>
              )}
            </Kart>

            <Kart baslik="Grup doluluğu" aciklama="Aktif gruplar, program ve doluluk">
              {veri.gruplar.doluluk_listesi.length === 0 ? (
                <p className="text-sm text-metin-soluk">Aktif grup yok</p>
              ) : (
                <ul className="space-y-4">
                  {veri.gruplar.doluluk_listesi.map((x) => (
                    <li key={x.id}>
                      <div className="flex items-baseline justify-between gap-3">
                        <Link to={`/gruplar/${x.id}`} className="text-sm font-medium hover:text-altin-metin">{x.ad}</Link>
                        <span className="num text-sm text-metin-orta shrink-0">{x.ogrenci_sayisi}/{x.kontenjan}</span>
                      </div>
                      <div className="num mt-0.5 mb-2 text-xs text-metin-soluk">{programOzeti(x.program)}</div>
                      <DolulukCubugu dolu={x.ogrenci_sayisi} kontenjan={x.kontenjan} yalnizCubuk />
                    </li>
                  ))}
                </ul>
              )}
            </Kart>
          </div>

          <div className="grid gap-4 lg:grid-cols-3 items-start">
            <Kart baslik="Son kayıtlar" aciklama="En son eklenen aktif öğrenciler" bosluksuz>
              {veri.son_kayitlar.length === 0 ? (
                <p className="px-6 pb-6 text-sm text-metin-soluk">Henüz kayıt yok</p>
              ) : (
                <ul className="border-t border-cizgi">
                  {veri.son_kayitlar.map((o) => (
                    <li key={o.id} className={`${listeSatiri} flex items-center gap-3 px-6 py-1 text-sm`}>
                      <OgrenciFoto id={o.id} fotoVar={o.foto_var} ad={o.ad} soyad={o.soyad} boyut="kucuk" sinif="size-8 rounded-full text-[10px]" />
                      <Link to={`/ogrenciler/${o.id}`} className="font-medium hover:text-altin-metin min-w-0 truncate">{o.ad} {o.soyad}</Link>
                      <span className="num ml-auto text-xs text-metin-soluk shrink-0">{TARIH.format(new Date(`${o.kayit_tarihi}T00:00:00`))}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Kart>
            <ResitKarti liste={resit} hata={resitHata} yenile={resitYukle} />
            <Kart baslik="Dikkat" aciklama="Tamamlanması gereken kayıtlar" bosluksuz>
              <ul className="border-t border-cizgi">
                {[
                  { ad: "Hesabı olmayan aktif öğrenci", sayi: veri.hesapsiz_aktif_ogrenci },
                  { ad: "Grubu olmayan aktif öğrenci", sayi: veri.grupsuz_aktif_ogrenci },
                ].map((d) => (
                  <li key={d.ad} className={listeSatiri}>
                    <Link to="/ogrenciler" className="flex items-center justify-between gap-3 px-6 min-h-[52px] text-sm hover:bg-yuzey-yuksek">
                      <span>{d.ad}</span>
                      <span className={`num ${d.sayi > 0 ? "font-semibold text-uyari" : "text-metin-soluk"}`}>{d.sayi}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </Kart>
          </div>
        </>
      )}
    </div>
  );
}

function Ozet({ v, bugunSayi, bugunOgrenci }: { v: GenelBakisVerisi; bugunSayi: number | null; bugunOgrenci: number }) {
  const g = v.gruplar;
  const oran = g.toplam_kontenjan > 0 ? Math.round((g.dolu / g.toplam_kontenjan) * 100) : 0;
  return (
    <div className="grid gap-4 grid-cols-2 md:grid-cols-3 xl:grid-cols-5 mb-4">
      <OzetKarti etiket="Aktif öğrenci" deger={v.ogrenci.aktif} ipucu={`+${v.ogrenci.bu_ay_kayit} bu ay`} />
      <OzetKarti etiket="Grup doluluğu" deger={`%${oran}`} ipucu={`${g.toplam_kontenjan} kontenjan`} ton="altin" />
      <OzetKarti etiket="Aktif antrenör" deger={v.antrenor.aktif} />
      <OzetKarti
        etiket="Bekleyen ödeme"
        deger={v.bekleyen_odeme.toplam_tutar === null ? paraBicimle(null) : PARA.format(Number(v.bekleyen_odeme.toplam_tutar))}
        ipucu={`${v.bekleyen_odeme.adet} kayıt`}
        ton={v.bekleyen_odeme.adet > 0 ? "uyari" : "normal"}
      />
      <OzetKarti
        etiket="Bugünkü ders"
        deger={bugunSayi ?? "—"}
        ipucu={bugunSayi === null ? undefined : `${bugunOgrenci} öğrenci`}
      />
    </div>
  );
}
