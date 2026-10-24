import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { resitUyarilariniGetir, type ResitUyarisi } from "../api/ogrenci";
import { genelBakisiGetir, type GenelBakisVerisi } from "../api/genelBakis";
import DolulukCubugu from "../components/DolulukCubugu";
import OgrenciFoto from "../components/OgrenciFoto";
import ResitGecisi from "../components/ResitGecisi";
import { hataMesaji } from "../lib/dogrulama";

const ROL_ADI: Record<string, string> = { anne: "Anne", baba: "Baba", diger: "Diğer", kendisi: "Kendisi" };

function ResitKarti() {
  const [liste, setListe] = useState<ResitUyarisi[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [secili, setSecili] = useState<ResitUyarisi | null>(null);
  const [bilgi, setBilgi] = useState<string | null>(null);

  const yukle = useCallback(async () => {
    try {
      setListe(await resitUyarilariniGetir());
      setHata(null);
    } catch (e) {
      setHata(hataMesaji(e));
    }
  }, []);

  useEffect(() => {
    void yukle();
  }, [yukle]);

  return (
    <section className="bg-yuzey border border-cizgi rounded-2xl p-4 sm:p-6">
      <h2 className="font-semibold mb-3">Reşit olan öğrenciler</h2>
      {bilgi && <p role="status" className="mb-3 rounded-lg border border-altin/60 bg-altin/10 text-altin-acik text-sm px-3 py-2">{bilgi}</p>}
      {hata && <p role="alert" className="text-sm text-hata">{hata}</p>}
      {!hata && liste === null && <p className="text-sm text-metin-soluk">Yükleniyor…</p>}
      {liste && liste.length === 0 && <p className="text-sm text-metin-soluk">Bekleyen reşit geçişi yok</p>}
      {liste && liste.length > 0 && (
        <ul className="space-y-2">
          {liste.map((o) => (
            <li key={o.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-cizgi px-3 py-2 text-sm">
              <div className="min-w-0">
                <Link to={`/ogrenciler/${o.id}`} className="font-medium hover:text-altin">{o.ad} {o.soyad}</Link>
                <div className="text-xs text-metin-soluk">
                  {o.yas} yaş • Birincil: {o.birincil_rol ? (ROL_ADI[o.birincil_rol] ?? o.birincil_rol) : "—"} • Veli hesabı: {o.veli_hesabi_var ? "var" : "yok"}
                </div>
              </div>
              <button
                className="rounded-lg border border-cizgi px-3 py-1.5 text-sm hover:border-altin"
                onClick={() => { setBilgi(null); setSecili(o); }}
              >
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
            void yukle();
          }}
        />
      )}
    </section>
  );
}

const PARA = new Intl.NumberFormat("tr-TR", { style: "currency", currency: "TRY" });
const TARIH = new Intl.DateTimeFormat("tr-TR");

function Kutucuk({ baslik, deger, alt }: { baslik: string; deger: string | number; alt?: string }) {
  return (
    <div className="bg-yuzey border border-cizgi rounded-2xl p-4">
      <div className="text-xs text-metin-soluk">{baslik}</div>
      <div className="text-2xl font-semibold mt-1">{deger}</div>
      {alt && <div className="text-xs text-metin-soluk mt-1">{alt}</div>}
    </div>
  );
}

function Kart({ baslik, children }: { baslik: string; children: React.ReactNode }) {
  return (
    <section className="bg-yuzey border border-cizgi rounded-2xl p-4 sm:p-6">
      <h2 className="font-semibold mb-3">{baslik}</h2>
      {children}
    </section>
  );
}

function Ozet({ v }: { v: GenelBakisVerisi }) {
  const g = v.gruplar;
  const oran = g.toplam_kontenjan > 0 ? Math.round((g.dolu / g.toplam_kontenjan) * 100) : 0;
  const dikkat = [
    { ad: "Hesabı olmayan aktif öğrenci", sayi: v.hesapsiz_aktif_ogrenci },
    { ad: "Grubu olmayan aktif öğrenci", sayi: v.grupsuz_aktif_ogrenci },
  ];
  return (
    <>
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4 mb-4">
        <Kutucuk baslik="Aktif öğrenci" deger={v.ogrenci.aktif} alt={`bu ay +${v.ogrenci.bu_ay_kayit} yeni`} />
        <Kutucuk baslik="Aktif grup" deger={g.aktif_grup} alt={`Toplam doluluk %${oran}`} />
        <Kutucuk baslik="Aktif antrenör" deger={v.antrenor.aktif} />
        <Kutucuk
          baslik="Bekleyen ödeme"
          deger={PARA.format(Number(v.bekleyen_odeme.toplam_tutar))}
          alt={`${v.bekleyen_odeme.adet} kayıt`}
        />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Kart baslik="Dikkat gerekenler">
          <ul className="space-y-2">
            {dikkat.map((d) => (
              <li key={d.ad}>
                <Link
                  to="/ogrenciler"
                  className="flex items-center justify-between rounded-xl border border-cizgi px-3 py-2 text-sm hover:border-altin"
                >
                  <span>{d.ad}</span>
                  <span className={d.sayi > 0 ? "font-semibold text-altin" : "text-metin-soluk"}>{d.sayi}</span>
                </Link>
              </li>
            ))}
          </ul>
        </Kart>
        <Kart baslik="Grup doluluğu">
          {g.doluluk_listesi.length === 0 ? (
            <p className="text-sm text-metin-soluk">Aktif grup yok</p>
          ) : (
            <ul className="space-y-3">
              {g.doluluk_listesi.map((x) => (
                <li key={x.id}>
                  <Link to={`/gruplar/${x.id}`} className="text-sm font-medium hover:text-altin">{x.ad}</Link>
                  <DolulukCubugu dolu={x.ogrenci_sayisi} kontenjan={x.kontenjan} />
                </li>
              ))}
            </ul>
          )}
        </Kart>
        <Kart baslik="Son kayıtlar">
          {v.son_kayitlar.length === 0 ? (
            <p className="text-sm text-metin-soluk">Henüz kayıt yok</p>
          ) : (
            <ul className="space-y-2">
              {v.son_kayitlar.map((o) => (
                <li key={o.id} className="flex items-center gap-3 text-sm">
                  <OgrenciFoto id={o.id} fotoVar={o.foto_var} ad={o.ad} soyad={o.soyad} boyut="kucuk" sinif="size-9 rounded-full" />
                  <Link to={`/ogrenciler/${o.id}`} className="font-medium hover:text-altin min-w-0 truncate">{o.ad} {o.soyad}</Link>
                  <span className="ml-auto text-xs text-metin-soluk shrink-0">{TARIH.format(new Date(`${o.kayit_tarihi}T00:00:00`))}</span>
                </li>
              ))}
            </ul>
          )}
        </Kart>
        <ResitKarti />
      </div>
    </>
  );
}

export default function GenelBakis() {
  const [veri, setVeri] = useState<GenelBakisVerisi | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    let iptal = false;
    genelBakisiGetir()
      .then((v) => { if (!iptal) setVeri(v); })
      .catch((e) => { if (!iptal) setHata(hataMesaji(e)); });
    return () => { iptal = true; };
  }, []);

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Genel bakış</h1>
      {hata && <p role="alert" className="text-sm text-hata mb-4">{hata}</p>}
      {!hata && veri === null && <p className="text-sm text-metin-soluk mb-4">Yükleniyor…</p>}
      {veri ? (
        <Ozet v={veri} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <ResitKarti />
        </div>
      )}
    </div>
  );
}
