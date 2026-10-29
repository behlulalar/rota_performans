import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { YONTEM_ETIKET } from "../api/odeme";
import type { HakTur, Sayac } from "../api/ogrenci";
import { cocukGetir, type CocukDetay, type VeliDers, type VeliPaket } from "../api/veli";
import Kart from "../components/Kart";
import OgrenciFoto from "../components/OgrenciFoto";
import SayfaBasligi from "../components/SayfaBasligi";
import { ApiHata } from "../lib/api";
import { hataMesaji, tarihBicimle } from "../lib/dogrulama";
import { paraBicimle } from "../lib/para";
import { GUNLER, saat } from "../lib/program";
import { dugme, listeSatiri, rozetBasari, rozetBirincil, rozetHata, rozetNotr, rozetUyari, uyariKutusu } from "../lib/stil";
import { tarihCoz } from "../lib/tarih";
import { dersMetni } from "./VeliAna";

const TUR_ETIKET: Record<HakTur, string> = {
  paket_yuklemesi: "Paket yüklendi",
  ders_kullanimi: "Derse katıldı",
  devamsizlik: "Devamsızlık (telafi hakkı doğdu)",
  telafi_kullanimi: "Telafi dersine katıldı",
  manuel_duzeltme: "Kulüp düzeltmesi",
  iptal: "Düzeltme",
};
const SEKMELER = [
  { anahtar: "yaklasan", ad: "Yaklaşan dersler" },
  { anahtar: "program", ad: "Haftalık program" },
  { anahtar: "paket", ad: "Paket ve ödemeler" },
  { anahtar: "gecmis", ad: "Son dersler" },
  { anahtar: "hareket", ad: "Ders hakkım" },
] as const;
const SAYAC_ETIKET: Record<Sayac, string> = { normal: "Kalan ders", telafi: "Telafi" };

const SAYI_TONU = {
  basari: "text-basari",
  uyari: "text-uyari",
  hata: "text-hata",
  vurgu: "text-altin-metin",
} as const;

function Sayi({ ad, deger, ton, alt }: { ad: string; deger: number; ton?: keyof typeof SAYI_TONU; alt?: string }) {
  return (
    <div className="rounded-[12px] border border-cizgi bg-zemin px-3 py-3 min-w-0">
      <div className="text-[12px] text-metin-soluk leading-4">{ad}</div>
      <div className={`num font-display text-[28px] leading-[1.15] mt-1 ${ton ? SAYI_TONU[ton] : ""}`}>{deger}</div>
      {alt && <div className="num text-xs text-metin-soluk mt-0.5">{alt}</div>}
    </div>
  );
}

function DersSatiri({ d, yoklamaGoster = false }: { d: VeliDers; yoklamaGoster?: boolean }) {
  return (
    <li className={`${listeSatiri} py-2.5 flex flex-wrap items-center justify-between gap-x-4 gap-y-1`}>
      <div className="min-w-0">
        <div className="num text-sm font-medium">{dersMetni(d)}</div>
        <div className="text-[13px] text-metin-soluk">{d.grup_ad}</div>
      </div>
      <div className="flex items-center gap-1.5">
        {d.telafi_mi && <span className={rozetBirincil}>Telafi</span>}
        {yoklamaGoster &&
          (d.yoklama === "geldi" ? (
            <span className={rozetBasari}>Geldi</span>
          ) : d.yoklama === "gelmedi" ? (
            <span className={rozetHata}>Gelmedi</span>
          ) : (
            <span className={rozetNotr}>Kayıt yok</span>
          ))}
      </div>
    </li>
  );
}

function PaketSatiri({ p }: { p: VeliPaket }) {
  const odenmis = p.durum === "odendi";
  return (
    <li className="px-6 py-4 border-t border-cizgi first:border-t-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-medium">
          {p.paket_adi} <span className="text-metin-soluk font-normal">· {p.ders_sayisi} ders</span>
        </div>
        <span className={odenmis ? rozetBasari : rozetUyari}>{odenmis ? "Ödendi" : "Ödeme bekliyor"}</span>
      </div>
      <div className="num mt-1 text-sm text-metin-soluk">
        Tutar {paraBicimle(p.uygulanan_fiyat)}
        {!odenmis && <> · Ödenen {paraBicimle(p.toplam_odenen)}</>}
        {p.baslangic && <> · {tarihBicimle(p.baslangic)}</>}
      </div>
      {p.odemeler.length > 0 && (
        <ul className="mt-2 space-y-1">
          {p.odemeler.map((o, i) => (
            <li key={i} className={`num text-[13px] flex flex-wrap gap-x-3 ${o.iptal ? "text-metin-soluk line-through" : ""}`}>
              <span>{tarihBicimle(o.tarih)}</span>
              <span>{paraBicimle(o.tutar)}</span>
              <span>{YONTEM_ETIKET[o.yontem]}</span>
              {o.iptal && <span className="no-underline">(iptal edildi)</span>}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export default function VeliCocuk() {
  const { id = "" } = useParams();
  const [c, setC] = useState<CocukDetay | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [hareketAcik, setHareketAcik] = useState(false);
  const [params, setParams] = useSearchParams();
  const sekme = SEKMELER.find((t) => t.anahtar === params.get("sekme"))?.anahtar ?? SEKMELER[0].anahtar;

  useEffect(() => {
    let iptal = false;
    setC(null);
    setHata(null);
    cocukGetir(id)
      .then((v) => !iptal && setC(v))
      .catch((e) => !iptal && setHata(e instanceof ApiHata && e.durum === 404 ? "Öğrenci bulunamadı." : hataMesaji(e)));
    return () => {
      iptal = true;
    };
  }, [id]);

  if (hata)
    return (
      <>
        <SayfaBasligi baslik="Öğrenci" />
        <p role="alert" className="text-sm text-hata">
          {hata}
        </p>
        <Link to="/panel" className={`${dugme} mt-4`}>
          Ana sayfaya dön
        </Link>
      </>
    );
  if (!c)
    return (
      <div role="status" aria-label="Yükleniyor" className="space-y-4">
        <div aria-hidden="true" className="animate-pulse rounded-[14px] bg-yuzey-yuksek h-20" />
        <div aria-hidden="true" className="animate-pulse rounded-[14px] bg-yuzey-yuksek h-28" />
        <div aria-hidden="true" className="animate-pulse rounded-[14px] bg-yuzey-yuksek h-56" />
      </div>
    );

  const h = c.ders_hakki;
  const o = c.ders_ozeti;
  const bekleyenler = c.paketler.filter((p) => p.durum === "odeme_bekliyor");
  return (
    <>
      <SayfaBasligi
        baslik={`${c.ad} ${c.soyad}`}
        aciklama={c.gruplar.length > 0 ? c.gruplar.map((g) => g.ad).join(" · ") : "Henüz bir gruba atanmadı"}
        rozet={c.durum === "pasif" ? <span className={rozetNotr}>Pasif</span> : undefined}
        eylemler={
          c.foto_var ? (
            <OgrenciFoto id={c.id} fotoVar ad={c.ad} soyad={c.soyad} boyut="buyuk" sinif="size-16 rounded-full" veli />
          ) : undefined
        }
      />

      {bekleyenler.length > 0 && (
        <p role="status" className={`${uyariKutusu} mb-5`}>
          Ödemesi bekleyen paket var: {bekleyenler.map((p) => `${p.paket_adi} (${paraBicimle(p.uygulanan_fiyat)})`).join(", ")}.
          Ödeme için lütfen kulüple iletişime geçin.
        </p>
      )}

      {c.ders_hakki_bitti && (
        <p role="status" className={`${uyariKutusu} mb-5`}>
          <span className="font-semibold">Ders hakkınız bitti.</span> Derslere devam edebilmek için lütfen kulüple iletişime geçip yeni paket alın.
        </p>
      )}

      <div className="grid grid-cols-3 gap-2 md:gap-4">
        <div className="bg-yuzey border border-cizgi rounded-[14px] px-3 py-4 md:p-5 min-w-0">
          <div className="text-[12px] md:text-[11px] font-semibold md:uppercase md:tracking-[0.12em] text-metin-soluk leading-4">Kalan ders</div>
          <div className={`num font-display text-[32px] leading-[1.15] mt-1.5 ${h.normal < 0 ? "text-hata" : ""}`}>{h.normal}</div>
        </div>
        <div className="bg-yuzey border border-cizgi rounded-[14px] px-3 py-4 md:p-5 min-w-0">
          <div className="text-[12px] md:text-[11px] font-semibold md:uppercase md:tracking-[0.12em] text-metin-soluk leading-4">Telafi hakkı</div>
          <div className={`num font-display text-[32px] leading-[1.15] mt-1.5 ${h.telafi < 0 ? "text-hata" : ""}`}>{h.telafi}</div>
          <div className="num text-xs text-metin-soluk mt-0.5">{h.kullanilabilir_telafi} planlanabilir</div>
        </div>
        <div className="bg-birincil border border-birincil rounded-[14px] px-3 py-4 md:p-5 min-w-0 text-birincil-metin">
          <div className="text-[12px] md:text-[11px] font-semibold md:uppercase md:tracking-[0.12em] leading-4 opacity-75">Sıradaki ders</div>
          {c.siradaki_ders ? (
            <>
              <div className="num font-display text-[19px] md:text-[28px] leading-[1.2] mt-2">
                {tarihCoz(c.siradaki_ders.tarih).toLocaleDateString("tr-TR", { weekday: "short" })} {saat(c.siradaki_ders.baslangic)}
              </div>
              <div className="num text-xs mt-0.5 opacity-75">
                {tarihCoz(c.siradaki_ders.tarih).toLocaleDateString("tr-TR", { day: "numeric", month: "long" })}
              </div>
            </>
          ) : (
            <div className="font-display text-[22px] leading-[1.2] mt-2">Yok</div>
          )}
        </div>
      </div>

      <div role="tablist" aria-label="Öğrenci bölümleri" className="mt-6 -mx-4 px-4 md:mx-0 md:px-0 flex gap-1 overflow-x-auto border-b border-cizgi">
        {SEKMELER.map((t) => {
          const sec = t.anahtar === sekme;
          return (
            <button
              key={t.anahtar}
              type="button"
              role="tab"
              id={`sekme-${t.anahtar}`}
              aria-selected={sec}
              aria-controls="sekme-icerik"
              onClick={() => setParams(t.anahtar === SEKMELER[0].anahtar ? {} : { sekme: t.anahtar }, { replace: true })}
              className={`shrink-0 px-3.5 min-h-11 -mb-px border-b-2 text-[14px] transition-colors ${
                sec ? "border-altin text-metin font-semibold" : "border-transparent text-metin-soluk hover:text-metin"
              }`}
            >
              {t.ad}
            </button>
          );
        })}
      </div>

      <div role="tabpanel" id="sekme-icerik" aria-labelledby={`sekme-${sekme}`} className="mt-4">
        {sekme === "yaklasan" && (
          <Kart baslik="Yaklaşan dersler" aciklama="Önümüzdeki 4 hafta" bosluksuz>
            {c.yaklasan_dersler.length === 0 ? (
              <p className="px-6 pb-6 text-sm text-metin-soluk">Planlanmış yaklaşan ders yok.</p>
            ) : (
              <ul className="px-6 pb-3">
                {c.yaklasan_dersler.map((d) => (
                  <DersSatiri key={d.oturum_id} d={d} />
                ))}
              </ul>
            )}
          </Kart>
        )}

        {sekme === "program" && (
          <Kart baslik="Haftalık program" bosluksuz>
            {c.program.length === 0 ? (
              <p className="px-6 pb-6 text-sm text-metin-soluk">Haftalık program yok.</p>
            ) : (
              <ul className="px-6 pb-3">
                {c.program.map((p, i) => (
                  <li key={i} className={`${listeSatiri} py-2.5 flex flex-wrap items-center justify-between gap-2`}>
                    <span className="text-sm font-medium">{GUNLER[p.gun - 1]}</span>
                    <span className="num text-sm text-metin-soluk">
                      {saat(p.baslangic)}–{saat(p.bitis)} · {p.grup_ad}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Kart>
        )}

        {sekme === "paket" && (
          <Kart baslik="Paket ve ödemeler" bosluksuz>
            {c.paketler.length === 0 ? (
              <p className="px-6 pb-6 text-sm text-metin-soluk">Henüz paket tanımlanmamış.</p>
            ) : (
              <ul className="pb-2">
                {c.paketler.map((p) => (
                  <PaketSatiri key={p.id} p={p} />
                ))}
              </ul>
            )}
          </Kart>
        )}

        {sekme === "gecmis" && (
          <Kart baslik="Son dersler" bosluksuz>
            {c.gecmis_dersler.length === 0 ? (
              <p className="px-6 pb-6 text-sm text-metin-soluk">Geçmiş ders kaydı yok.</p>
            ) : (
              <ul className="px-6 pb-3">
                {c.gecmis_dersler.map((d) => (
                  <DersSatiri key={d.oturum_id} d={d} yoklamaGoster />
                ))}
              </ul>
            )}
          </Kart>
        )}

        {sekme === "hareket" && (
          <div className="space-y-4">
            <Kart baslik="Ders hakkım" aciklama="Paketle gelen derslerin durumu" bosluksuz>
              <div className="px-6 pb-6">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-3">
                  <Sayi ad="Toplam ders" deger={o.toplam} />
                  <Sayi ad="Katıldığı" deger={o.katildi} ton="basari" />
                  <Sayi ad="Gelmediği" deger={o.devamsiz} ton={o.devamsiz > 0 ? "uyari" : undefined} />
                  <Sayi ad="Kalan" deger={o.kalan} ton={o.kalan < 0 ? "hata" : "vurgu"} />
                </div>
                {o.toplam > 0 && (
                  <div className="mt-4">
                    <div
                      role="img"
                      aria-label={`${o.toplam} dersin ${o.katildi} tanesine katıldı, ${o.devamsiz} tanesine gelmedi`}
                      className="h-2.5 rounded-full bg-yuzey-yuksek overflow-hidden flex"
                    >
                      <div className="bg-basari" style={{ width: `${Math.min(100, (o.katildi / o.toplam) * 100)}%` }} />
                      <div className="bg-uyari" style={{ width: `${Math.min(100, (o.devamsiz / o.toplam) * 100)}%` }} />
                    </div>
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-metin-soluk">
                      <span><span className="inline-block size-2 rounded-full bg-basari mr-1.5" />Katıldı</span>
                      <span><span className="inline-block size-2 rounded-full bg-uyari mr-1.5" />Gelmedi</span>
                      <span><span className="inline-block size-2 rounded-full bg-yuzey-yuksek border border-cizgi-guclu mr-1.5" />Kalan</span>
                    </div>
                  </div>
                )}
              </div>
            </Kart>

            <Kart baslik="Telafi hakkım" aciklama="Gelinmeyen derslerden doğan telafi hakları" bosluksuz>
              <div className="px-6 pb-6 grid grid-cols-3 gap-2 md:gap-3">
                <Sayi ad="Doğan" deger={o.telafi_dogan} />
                <Sayi ad="Kullanılan" deger={o.telafi_kullanilan} />
                <Sayi ad="Kalan" deger={o.telafi_kalan} ton={o.telafi_kalan < 0 ? "hata" : "vurgu"} alt={`${h.kullanilabilir_telafi} planlanabilir`} />
              </div>
            </Kart>

            <Kart bosluksuz>
              <div className="px-6 py-4">
                <button
                  type="button"
                  className="text-[13px] font-semibold hover:text-altin-metin min-h-11 md:min-h-0"
                  aria-expanded={hareketAcik}
                  onClick={() => setHareketAcik((a) => !a)}
                >
                  {hareketAcik ? "▾" : "▸"} Tüm hareketleri göster
                </button>
                {hareketAcik &&
                  (c.hareketler.length === 0 ? (
                    <p className="mt-2 text-sm text-metin-soluk">Henüz hareket yok.</p>
                  ) : (
                    <ul className="mt-2 divide-y divide-cizgi border-y border-cizgi">
                      {c.hareketler.map((x, i) => (
                        <li key={i} className="py-2.5 text-sm flex flex-wrap items-center justify-between gap-2">
                          <span>
                            <span className="font-medium">{TUR_ETIKET[x.tur] ?? x.tur}</span>{" "}
                            <span className="text-metin-soluk">· {SAYAC_ETIKET[x.sayac]}</span>
                          </span>
                          <span className="num flex items-center gap-3">
                            <span className="text-metin-soluk">{tarihBicimle(x.zaman)}</span>
                            <span className={`font-medium ${x.miktar < 0 ? "text-hata" : "text-basari"}`}>
                              {x.miktar > 0 ? `+${x.miktar}` : x.miktar}
                            </span>
                          </span>
                        </li>
                      ))}
                    </ul>
                  ))}
              </div>
            </Kart>
          </div>
        )}
      </div>
    </>
  );
}
