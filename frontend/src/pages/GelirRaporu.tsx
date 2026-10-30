import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { gelirCsvIndir, gelirRaporuGetir, YONTEM_ETIKET, type GelirRaporu as Rapor } from "../api/rapor";
import FinansNotu, { useTutarGizli } from "../components/FinansNotu";
import Kart from "../components/Kart";
import SayfaBasligi from "../components/SayfaBasligi";
import { hataMesaji } from "../lib/dogrulama";
import { paraBicimle } from "../lib/para";
import { dugme, rozetBasari, rozetHata, rozetNotr } from "../lib/stil";

const ayAdi = (yil: number, ay: number) => new Date(yil, ay - 1, 1).toLocaleDateString("tr-TR", { month: "long", year: "numeric" });
const kisaAy = (ay: number) => new Date(2000, ay - 1, 1).toLocaleDateString("tr-TR", { month: "short" });
const sayi = (d: string | number | null) => Number(d) || 0;
const yuzdeYaz = (d: number | string) => `%${sayi(d).toLocaleString("tr-TR", { maximumFractionDigits: 1 })}`;

const kpiKutu = "bg-yuzey border border-cizgi rounded-[14px] p-5 min-w-0";
const kpiEtiket = "text-[11px] font-semibold uppercase tracking-[0.12em] text-metin-soluk";
const kpiDeger = "num font-display text-[32px] leading-[1.15] mt-2";

/** Dikey çubuk grafiği: HTML/CSS, tema token'larıyla. Çubuklar düğmedir (dokunma/odak/klavye). */
type Cubuk = { anahtar: string; deger: number; etiket: string; metin: string; vurgulu?: boolean; etiketGoster: boolean };
function CubukGrafik({
  cubuklar, onSec, secili, yukseklik = "h-40", okuma,
}: {
  cubuklar: Cubuk[];
  onSec?: (anahtar: string) => void;
  secili?: string | null;
  yukseklik?: string;
  okuma?: (c: Cubuk) => string;
}) {
  const enBuyuk = Math.max(1, ...cubuklar.map((c) => c.deger));
  const dar = cubuklar.length > 14;
  return (
    <div>
      <div className={`flex items-end ${dar ? "gap-[2px]" : "gap-1.5"} ${yukseklik} border-b border-cizgi-guclu relative`}>
        <div className="absolute inset-x-0 top-0 border-t border-dashed border-cizgi" aria-hidden="true" />
        <span aria-hidden="true" className="absolute left-0 -top-0.5 -translate-y-full num text-[10px] text-metin-soluk">{paraBicimle(enBuyuk)}</span>
        {cubuklar.map((c) => {
          const yuk = c.deger > 0 ? Math.max(3, (c.deger / enBuyuk) * 100) : 0;
          const secildi = secili === c.anahtar;
          return (
            <button
              key={c.anahtar}
              type="button"
              tabIndex={onSec ? 0 : -1}
              onClick={() => onSec?.(c.anahtar)}
              title={okuma ? okuma(c) : c.metin}
              aria-label={c.metin}
              aria-pressed={secili === c.anahtar}
              className={`group relative flex-1 min-w-0 h-full flex items-end justify-center outline-none ${onSec ? "cursor-pointer" : "cursor-default"}`}
            >
              <span
                aria-hidden="true"
                className={`block w-full ${dar ? "max-w-3" : "max-w-9"} rounded-t-[3px] transition-colors group-focus-visible:outline group-focus-visible:outline-2 group-focus-visible:outline-altin ${c.vurgulu || secildi ? "bg-altin" : "bg-altin/40 group-hover:bg-altin/70"}`}
                style={{ height: `${yuk}%` }}
              />
            </button>
          );
        })}
      </div>
      <div className={`flex ${dar ? "gap-[2px]" : "gap-1.5"} mt-1.5`} aria-hidden="true">
        {cubuklar.map((c) => (
          <div key={c.anahtar} className={`flex-1 min-w-0 text-center text-[10px] sm:text-[11px] leading-4 overflow-visible whitespace-nowrap ${c.vurgulu || secili === c.anahtar ? "text-altin-metin font-semibold" : "text-metin-soluk"}`}>
            {c.etiketGoster ? c.etiket : ""}
          </div>
        ))}
      </div>
    </div>
  );
}

function Degisim({ r }: { r: Rapor }) {
  const d = r.ozet.degisim_yuzde;
  if (d === null || d === undefined) return <span className={rozetNotr}>Önceki ay verisi yok</span>;
  const n = sayi(d);
  const metin = `${Math.abs(n).toLocaleString("tr-TR", { maximumFractionDigits: 1 })}%`;
  if (n > 0) return <span className={rozetBasari}>▲ {metin} önceki aya göre</span>;
  if (n < 0) return <span className={rozetHata}>▼ {metin} önceki aya göre</span>;
  return <span className={rozetNotr}>= %0 önceki aya göre</span>;
}

export default function GelirRaporu() {
  const simdi = new Date();
  const buYil = simdi.getFullYear();
  const buAy = simdi.getMonth() + 1;
  const [donem, setDonem] = useState({ yil: buYil, ay: buAy });
  const [veri, setVeri] = useState<Rapor | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<string | null>(null);
  const [deneme, setDeneme] = useState(0);
  const [gunSecili, setGunSecili] = useState<string | null>(null);
  const gizli = useTutarGizli();
  const [csvDurum, setCsvDurum] = useState<{ yukleniyor: boolean; hata: string | null }>({ yukleniyor: false, hata: null });

  useEffect(() => {
    let iptal = false;
    setYukleniyor(true);
    setHata(null);
    setGunSecili(null);
    gelirRaporuGetir(donem.yil, donem.ay)
      .then((v) => !iptal && setVeri(v))
      .catch((e) => !iptal && setHata(hataMesaji(e)))
      .finally(() => !iptal && setYukleniyor(false));
    return () => { iptal = true; };
  }, [donem, deneme]);

  const gelecekte = donem.yil > buYil || (donem.yil === buYil && donem.ay >= buAy);
  const git = (fark: number) => {
    const d = new Date(donem.yil, donem.ay - 1 + fark, 1);
    const yeni = { yil: d.getFullYear(), ay: d.getMonth() + 1 };
    if (yeni.yil > buYil || (yeni.yil === buYil && yeni.ay > buAy)) return;
    setDonem(yeni);
  };

  const csv = async () => {
    if (!veri) return;
    setCsvDurum({ yukleniyor: true, hata: null });
    try {
      await gelirCsvIndir(veri.donem.baslangic, veri.donem.bitis);
      setCsvDurum({ yukleniyor: false, hata: null });
    } catch (e) {
      setCsvDurum({ yukleniyor: false, hata: hataMesaji(e) });
    }
  };

  const aylikCubuklar = useMemo<Cubuk[]>(() => (veri?.aylik_seri ?? []).map((a, i, h) => ({
    anahtar: `${a.yil}-${a.ay}`,
    deger: sayi(a.tutar),
    etiket: kisaAy(a.ay),
    metin: `${ayAdi(a.yil, a.ay)}: ${paraBicimle(a.tutar)} (${a.adet} ödeme)`,
    vurgulu: a.yil === donem.yil && a.ay === donem.ay,
    etiketGoster: h.length <= 12 || i % 2 === 0,
  })), [veri, donem]);

  const gunlukCubuklar = useMemo<Cubuk[]>(() => (veri?.gunluk ?? []).map((g) => {
    const gun = Number(g.tarih.slice(8, 10));
    const goster = gun === 1 || gun % 5 === 0;
    return {
      anahtar: g.tarih,
      deger: sayi(g.tutar),
      etiket: String(gun),
      metin: `${gun} ${ayAdi(donem.yil, donem.ay)}: ${paraBicimle(g.tutar)} (${g.adet} ödeme)`,
      etiketGoster: goster,
    };
  }), [veri, donem]);

  const bos = !!veri && veri.ozet.odeme_adedi === 0;
  const ayMetni = ayAdi(donem.yil, donem.ay);
  const gunSeciliKayit = veri?.gunluk.find((g) => g.tarih === gunSecili);

  return (
    <div className="space-y-6">
      <SayfaBasligi baslik="Gelir raporu" aciklama={`${ayMetni} · tahsilat, bekleyen alacak ve düzeltmeler`} />
      <FinansNotu />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1">
          <button className={dugme} onClick={() => git(-1)} aria-label="Önceki ay">‹</button>
          <span className="num min-w-40 text-center font-medium capitalize" aria-live="polite" data-testid="donem-adi">{ayMetni}</span>
          <button className={dugme} onClick={() => git(1)} disabled={gelecekte} aria-label="Sonraki ay">›</button>
        </div>
        {!gizli && (
          <div className="flex flex-col items-end gap-1">
            <button className={dugme} onClick={csv} disabled={!veri || csvDurum.yukleniyor}>
              {csvDurum.yukleniyor ? "İndiriliyor…" : "CSV indir (seçili ay)"}
            </button>
            {csvDurum.hata && <p role="alert" className="text-[13px] text-hata">{csvDurum.hata}</p>}
          </div>
        )}
      </div>

      {hata && (
        <div role="alert" className="bg-yuzey border border-hata/50 rounded-[14px] p-4 flex flex-wrap items-center justify-between gap-3">
          <span className="text-[13px] text-hata">{hata}</span>
          <button className={dugme} onClick={() => setDeneme((n) => n + 1)}>Yeniden dene</button>
        </div>
      )}

      {!veri ? (
        !hata && <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>
      ) : (
        <div className={`space-y-6 ${yukleniyor ? "opacity-60" : ""}`} aria-busy={yukleniyor}>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <div className={kpiKutu} data-testid="kpi-tahsilat">
              <div className={kpiEtiket}>Toplam tahsilat</div>
              <div className={`${kpiDeger} text-altin-metin`}>{paraBicimle(veri.ozet.toplam_tahsilat)}</div>
              {!gizli && <div className="mt-2"><Degisim r={veri} /></div>}
              {veri.ozet.degisim_yuzde !== null && <div className="num text-xs text-metin-soluk mt-1.5">Önceki ay: {paraBicimle(veri.ozet.onceki_ay_tahsilat)}</div>}
            </div>
            <div className={kpiKutu} data-testid="kpi-adet">
              <div className={kpiEtiket}>Ödeme adedi</div>
              <div className={kpiDeger}>{veri.ozet.odeme_adedi}</div>
              <div className="num text-xs text-metin-soluk mt-1">Ortalama ödeme: {paraBicimle(veri.ozet.ortalama_odeme)}</div>
            </div>
            <div className={kpiKutu} data-testid="kpi-bekleyen">
              <div className={kpiEtiket}>Bekleyen alacak</div>
              <div className={kpiDeger}>{paraBicimle(veri.bekleyen.tutar)}</div>
              <div className="num text-xs text-metin-soluk mt-1">{veri.bekleyen.adet} paket ödeme bekliyor</div>
              {veri.bekleyen.gecikmis_adet > 0 && (
                <div className="num text-xs text-hata font-medium mt-1">Gecikmiş: {paraBicimle(veri.bekleyen.gecikmis_tutar)} · {veri.bekleyen.gecikmis_adet} paket</div>
              )}
              <Link to="/odemeler" className="inline-block mt-2 text-[13px] text-altin-metin hover:underline">Ödemeler sayfasına git →</Link>
            </div>
            <div className={kpiKutu} data-testid="kpi-duzeltme">
              <div className={kpiEtiket}>Düzeltmeler</div>
              <dl className="mt-2 space-y-1.5 text-[13px]">
                <div className="flex justify-between gap-2"><dt className="text-metin-soluk">İptal edilen ödeme</dt><dd className="num text-right">{paraBicimle(veri.ozet.iptal_edilen_tutar)} <span className="text-metin-soluk">({veri.ozet.iptal_adedi})</span></dd></div>
                <div className="flex justify-between gap-2"><dt className="text-metin-soluk">Verilen indirim</dt><dd className="num">{paraBicimle(veri.ozet.indirim_toplami)}</dd></div>
                <div className="flex justify-between gap-2"><dt className="text-metin-soluk">Ücretsiz paket</dt><dd className="num">{veri.ozet.ucretsiz_paket_adedi}</dd></div>
              </dl>
            </div>
          </div>

          {gizli ? (
            <Kart>
              <p className="text-center text-metin-soluk py-6" data-testid="tutar-gizli">Teknik destek hesabında tutarlar gizlidir.</p>
            </Kart>
          ) : (
            <>
            <Kart baslik="Son 12 ay tahsilat" aciklama="Bir aya tıklayarak o aya geçin">
              <CubukGrafik
                cubuklar={aylikCubuklar}
                secili={`${donem.yil}-${donem.ay}`}
                onSec={(k) => { const [y, a] = k.split("-").map(Number); setDonem({ yil: y, ay: a }); }}
                okuma={(c) => c.metin}
              />
              <table className="sr-only" aria-label="Son 12 ay tahsilat tablosu">
                <thead><tr><th>Ay</th><th>Tutar</th><th>Ödeme adedi</th></tr></thead>
                <tbody>{veri.aylik_seri.map((a) => <tr key={`${a.yil}-${a.ay}`}><td>{ayAdi(a.yil, a.ay)}</td><td>{paraBicimle(a.tutar)}</td><td>{a.adet}</td></tr>)}</tbody>
              </table>
            </Kart>

            {bos ? (
              <Kart>
                <p className="text-center text-metin-soluk py-6" data-testid="bos-donem">Bu ayda tahsilat yok ({ayMetni}).</p>
              </Kart>
            ) : (
              <>
                <Kart
                  baslik="Günlük tahsilat"
                  aciklama={gunSeciliKayit ? <span className="num">{gunSeciliKayit.tarih.slice(8, 10)} {ayMetni}: {paraBicimle(gunSeciliKayit.tutar)} · {gunSeciliKayit.adet} ödeme</span> : `${ayMetni} · bir güne dokunarak tutarını görün`}
                >
                  <div className="pt-4">
                    <CubukGrafik cubuklar={gunlukCubuklar} secili={gunSecili} onSec={(k) => setGunSecili((s) => (s === k ? null : k))} />
                  </div>
                  <table className="sr-only" aria-label="Günlük tahsilat tablosu">
                    <thead><tr><th>Tarih</th><th>Tutar</th><th>Ödeme adedi</th></tr></thead>
                    <tbody>{veri.gunluk.map((g) => <tr key={g.tarih}><td>{g.tarih}</td><td>{paraBicimle(g.tutar)}</td><td>{g.adet}</td></tr>)}</tbody>
                  </table>
                </Kart>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <Kart baslik="Yönteme göre dağılım">
                    <ul className="space-y-3" data-testid="yontem-dagilimi">
                      {veri.yontem_dagilimi.map((d) => (
                        <li key={d.yontem} className="text-[13px]">
                          <div className="flex justify-between gap-2">
                            <span>{YONTEM_ETIKET[d.yontem]} <span className="text-metin-soluk">({d.adet})</span></span>
                            <span className="num">{paraBicimle(d.tutar)} <span className="text-metin-soluk">· {yuzdeYaz(d.yuzde)}</span></span>
                          </div>
                          <div className="h-2 rounded-full bg-yuzey-yuksek mt-1.5" role="img" aria-label={`${YONTEM_ETIKET[d.yontem]} ${yuzdeYaz(d.yuzde)}`}>
                            <div className="h-full rounded-full bg-altin" style={{ width: `${Math.min(100, Math.max(2, sayi(d.yuzde)))}%` }} />
                          </div>
                        </li>
                      ))}
                    </ul>
                  </Kart>
                  <Kart baslik="Pakete göre dağılım" bosluksuz>
                    <div className="border-t border-cizgi" data-testid="paket-dagilimi">
                      {veri.paket_dagilimi.length === 0 ? (
                        <p className="text-sm text-metin-soluk px-6 py-4">Paket verisi yok.</p>
                      ) : (() => {
                        const enBuyuk = Math.max(1, ...veri.paket_dagilimi.map((p) => sayi(p.tutar)));
                        return (
                          <ul>
                            {veri.paket_dagilimi.map((p) => (
                              <li key={p.paket_adi} className="px-6 py-3 border-t border-cizgi first:border-t-0 text-[13px]">
                                <div className="flex justify-between gap-3">
                                  <span className="min-w-0 break-words">{p.paket_adi} <span className="text-metin-soluk">({p.adet})</span></span>
                                  <span className="num shrink-0">{paraBicimle(p.tutar)}</span>
                                </div>
                                <div className="h-1.5 rounded-full bg-yuzey-yuksek mt-1.5"><div className="h-full rounded-full bg-altin" style={{ width: `${Math.max(2, (sayi(p.tutar) / enBuyuk) * 100)}%` }} /></div>
                              </li>
                            ))}
                          </ul>
                        );
                      })()}
                    </div>
                  </Kart>
                </div>
              </>
            )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
