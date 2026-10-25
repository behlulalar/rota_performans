import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  bekleyenOdemeleriGetir, odemeleriGetir, YONTEM_ETIKET,
  type BekleyenOdeme, type OdemeKaydi, type OdemeListesi,
} from "../api/odeme";
import Kart from "../components/Kart";
import OdemeAlPenceresi, { type OdemeHedefi } from "../components/OdemeAlPenceresi";
import OzetKarti from "../components/OzetKarti";
import SayfaBasligi from "../components/SayfaBasligi";
import { hataMesaji, tarihBicimle } from "../lib/dogrulama";
import { paraBicimle } from "../lib/para";
import { dugme, girdi, rozetBasari, rozetHata, rozetNotr, satir, secimKutusu, td, th } from "../lib/stil";
import { yyyyAyGun } from "../lib/tarih";

const BOYUT = 20;

function ayAraligi(d: Date) {
  return { baslangic: yyyyAyGun(new Date(d.getFullYear(), d.getMonth(), 1)), bitis: yyyyAyGun(new Date(d.getFullYear(), d.getMonth() + 1, 0)) };
}
const ayEtiketi = (d: Date) => d.toLocaleDateString("tr-TR", { month: "long", year: "numeric" });

function Bekleyenler({ surum, onOdemeAl }: { surum: number; onOdemeAl: (h: OdemeHedefi) => void }) {
  const [liste, setListe] = useState<BekleyenOdeme[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    let iptal = false;
    bekleyenOdemeleriGetir()
      .then((v) => { if (!iptal) { setListe(v); setHata(null); } })
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => { iptal = true; };
  }, [surum]);

  const gun = (b: BekleyenOdeme) => <span className={`num ${b.bekleme_gun >= 7 ? "text-hata font-medium" : "text-metin-soluk"}`}>{b.bekleme_gun} gün</span>;
  const al = (b: BekleyenOdeme) => (
    <button
      className={dugme}
      aria-label={`${b.ogrenci.ad} ${b.ogrenci.soyad} için ödeme al`}
      onClick={() => onOdemeAl({ ogrenciPaketiId: b.ogrenci_paketi_id, paketAdi: b.paket_adi, tutar: b.uygulanan_fiyat, ogrenciAdi: `${b.ogrenci.ad} ${b.ogrenci.soyad}` })}
    >Ödeme al</button>
  );

  return (
    <Kart baslik="Ödeme bekleyenler" aciklama={liste ? `${liste.length} paket ödeme bekliyor · en eski önce` : undefined} bosluksuz>
      <div className="border-t border-cizgi" data-testid="bekleyenler">
        {hata && <p role="alert" className="text-[13px] text-hata px-6 py-3">{hata}</p>}
        {!liste ? (
          !hata && <p className="text-sm text-metin-soluk px-6 py-4">Yükleniyor…</p>
        ) : liste.length === 0 ? (
          <p className="text-sm text-metin-soluk px-6 py-4">Ödeme bekleyen paket yok.</p>
        ) : (
          <>
            <div className="hidden md:block">
              <table className="w-full text-[13px]">
                <thead><tr>
                  <th className={th}>Öğrenci</th><th className={th}>Paket</th><th className={th}>Tutar</th><th className={th}>Atama</th><th className={th}>Bekleme</th><th className={th}></th>
                </tr></thead>
                <tbody>
                  {liste.map((b) => (
                    <tr key={b.ogrenci_paketi_id} className={satir}>
                      <td className={`${td} font-medium`}><Link to={`/ogrenciler/${b.ogrenci.id}`} className="hover:text-altin-metin">{b.ogrenci.ad} {b.ogrenci.soyad}</Link></td>
                      <td className={td}>{b.paket_adi}</td>
                      <td className={`${td} num`}>{paraBicimle(b.uygulanan_fiyat)}</td>
                      <td className={`${td} num text-metin-orta`}>{tarihBicimle(b.atama_tarihi.slice(0, 10))}</td>
                      <td className={td}>{gun(b)}</td>
                      <td className={`${td} text-right`}>{al(b)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="md:hidden">
              {liste.map((b) => (
                <li key={b.ogrenci_paketi_id} className="px-4 py-3 border-t border-cizgi first:border-t-0 space-y-1">
                  <div className="flex items-start justify-between gap-2">
                    <Link to={`/ogrenciler/${b.ogrenci.id}`} className="font-medium hover:text-altin-metin">{b.ogrenci.ad} {b.ogrenci.soyad}</Link>
                    {gun(b)}
                  </div>
                  <div className="text-[13px] text-metin-soluk">{b.paket_adi} · <span className="num">{paraBicimle(b.uygulanan_fiyat)}</span></div>
                  {al(b)}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </Kart>
  );
}

export default function OdemeListe() {
  const [ay, setAy] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [aralik, setAralik] = useState(() => ayAraligi(new Date()));
  const [yontem, setYontem] = useState("");
  const [arama, setArama] = useState("");
  const [q, setQ] = useState("");
  const [sayfa, setSayfa] = useState(1);
  const [veri, setVeri] = useState<OdemeListesi | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<string | null>(null);
  const [surum, setSurum] = useState(0);
  const [odemeHedefi, setOdemeHedefi] = useState<OdemeHedefi | null>(null);

  useEffect(() => {
    const t = setTimeout(() => { setQ(arama.trim()); setSayfa(1); }, 300);
    return () => clearTimeout(t);
  }, [arama]);

  useEffect(() => {
    let iptal = false;
    setYukleniyor(true);
    setHata(null);
    odemeleriGetir({ ...aralik, yontem: yontem || undefined, q: q || undefined, sayfa, boyut: BOYUT, iptal_dahil: true })
      .then((v) => !iptal && setVeri(v))
      .catch((e) => !iptal && setHata(hataMesaji(e)))
      .finally(() => !iptal && setYukleniyor(false));
    return () => { iptal = true; };
  }, [aralik, yontem, q, sayfa, surum]);

  const ayDegistir = useCallback((fark: number) => {
    const y = new Date(ay.getFullYear(), ay.getMonth() + fark, 1);
    setAy(y);
    setAralik(ayAraligi(y));
    setSayfa(1);
  }, [ay]);
  const buAy = () => { const y = new Date(); const b = new Date(y.getFullYear(), y.getMonth(), 1); setAy(b); setAralik(ayAraligi(b)); setSayfa(1); };
  const ozelAralik = (alan: "baslangic" | "bitis", deger: string) => {
    if (!deger) return;
    setAralik((a) => ({ ...a, [alan]: deger }));
    setSayfa(1);
  };

  const sayfaSayisi = veri ? Math.max(1, Math.ceil(veri.toplam / veri.boyut)) : 1;
  const enBuyuk = Math.max(1, ...(veri?.ozet.yontem_dagilimi ?? []).map((d) => Number(d.tutar)));

  const durum = (o: OdemeKaydi) => <span className={o.iptal ? rozetHata : rozetBasari}>{o.iptal ? "Geri alındı" : "Alındı"}</span>;
  const neden = (o: OdemeKaydi) => o.iptal && o.iptal_nedeni ? <div className="text-xs text-metin-soluk">Neden: {o.iptal_nedeni}</div> : null;

  return (
    <div className="space-y-6">
      <SayfaBasligi baslik="Ödemeler" aciklama={`${ayEtiketi(ay)} dönemi · tahsilatlar ve ödeme bekleyenler`} />

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex items-center gap-1">
          <button className={dugme} onClick={() => ayDegistir(-1)} aria-label="Önceki ay">‹</button>
          <span className="num min-w-36 text-center font-medium capitalize" aria-live="polite">{ayEtiketi(ay)}</span>
          <button className={dugme} onClick={() => ayDegistir(1)} aria-label="Sonraki ay">›</button>
          <button className={dugme} onClick={buAy}>Bu ay</button>
        </div>
        <label className="block"><span className="text-xs text-metin-soluk">Başlangıç</span>
          <input type="date" className={`${girdi} mt-0.5`} value={aralik.baslangic} max={aralik.bitis} onChange={(e) => ozelAralik("baslangic", e.target.value)} aria-label="Başlangıç tarihi" /></label>
        <label className="block"><span className="text-xs text-metin-soluk">Bitiş</span>
          <input type="date" className={`${girdi} mt-0.5`} value={aralik.bitis} min={aralik.baslangic} onChange={(e) => ozelAralik("bitis", e.target.value)} aria-label="Bitiş tarihi" /></label>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <OzetKarti etiket="Toplam tahsilat" deger={veri ? paraBicimle(veri.ozet.toplam_tutar) : "—"} ton="altin" ipucu="İptal edilenler hariç" />
        <OzetKarti etiket="Ödeme adedi" deger={veri ? veri.ozet.adet : "—"} />
        <div className="bg-yuzey border border-cizgi rounded-[5px] p-5 min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-metin-soluk">Yönteme göre</div>
          {!veri || veri.ozet.yontem_dagilimi.length === 0 ? (
            <p className="text-sm text-metin-soluk mt-2">Bu dönemde ödeme yok.</p>
          ) : (
            <ul className="mt-2 space-y-2">
              {veri.ozet.yontem_dagilimi.map((d) => (
                <li key={d.yontem} className="text-[13px]">
                  <div className="flex justify-between gap-2"><span>{YONTEM_ETIKET[d.yontem]} <span className="text-metin-soluk">({d.adet})</span></span><span className="num">{paraBicimle(d.tutar)}</span></div>
                  <div className="h-1.5 rounded-full bg-yuzey-yuksek mt-1"><div className="h-full rounded-full bg-altin" style={{ width: `${Math.max(4, (Number(d.tutar) / enBuyuk) * 100)}%` }} /></div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <Bekleyenler surum={surum} onOdemeAl={setOdemeHedefi} />

      <div className="flex flex-wrap gap-3">
        <select value={yontem} onChange={(e) => { setYontem(e.target.value); setSayfa(1); }} aria-label="Yöntem filtresi" className={secimKutusu}>
          <option value="">Tüm yöntemler</option>
          {Object.entries(YONTEM_ETIKET).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input type="search" value={arama} onChange={(e) => setArama(e.target.value)} placeholder="Öğrenci ara…" aria-label="Öğrenci ara" className={`${secimKutusu} flex-1 min-w-48 max-w-sm`} />
      </div>

      {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
      {!veri ? (
        !hata && <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>
      ) : veri.kayitlar.length === 0 ? (
        <div className="bg-yuzey border border-cizgi rounded-[5px] p-10 text-center text-metin-soluk">Bu dönemde ve filtrede ödeme kaydı yok.</div>
      ) : (
        <div className={yukleniyor ? "opacity-60" : ""}>
          <div className="hidden md:block bg-yuzey border border-cizgi rounded-[5px] overflow-hidden">
            <table className="w-full text-[13px]" aria-label="Ödemeler">
              <thead><tr>
                <th className={th}>Tarih</th><th className={th}>Öğrenci</th><th className={th}>Paket</th><th className={th}>Tutar</th><th className={th}>Yöntem</th><th className={th}>Alan</th><th className={th}>Durum</th>
              </tr></thead>
              <tbody>
                {veri.kayitlar.map((o) => (
                  <tr key={o.id} className={`${satir} ${o.iptal ? "opacity-60" : ""}`}>
                    <td className={`${td} num`}>{tarihBicimle(o.tarih)}</td>
                    <td className={`${td} font-medium`}><Link to={`/ogrenciler/${o.ogrenci.id}`} className="hover:text-altin-metin">{o.ogrenci.ad} {o.ogrenci.soyad}</Link></td>
                    <td className={td}>{o.paket_adi}</td>
                    <td className={`${td} num ${o.iptal ? "line-through" : ""}`}>{paraBicimle(o.tutar)}</td>
                    <td className={td}><span className={rozetNotr}>{YONTEM_ETIKET[o.yontem]}</span></td>
                    <td className={`${td} text-metin-orta`}>{o.alan_ad ?? "—"}</td>
                    <td className={`${td} py-1`}>{durum(o)}{neden(o)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="md:hidden space-y-2">
            {veri.kayitlar.map((o) => (
              <li key={o.id} className={`bg-yuzey border border-cizgi rounded-[5px] p-4 space-y-1 ${o.iptal ? "opacity-60" : ""}`}>
                <div className="flex items-start justify-between gap-2">
                  <Link to={`/ogrenciler/${o.ogrenci.id}`} className="font-medium hover:text-altin-metin">{o.ogrenci.ad} {o.ogrenci.soyad}</Link>
                  {durum(o)}
                </div>
                <div className="text-[13px] text-metin-soluk">{o.paket_adi}</div>
                <div className="flex justify-between gap-2 text-[13px]">
                  <span className={`num font-medium ${o.iptal ? "line-through" : ""}`}>{paraBicimle(o.tutar)}</span>
                  <span className="num text-metin-soluk">{tarihBicimle(o.tarih)} · {YONTEM_ETIKET[o.yontem]}</span>
                </div>
                {o.alan_ad && <div className="text-xs text-metin-soluk">Alan: {o.alan_ad}</div>}
                {neden(o)}
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

      {odemeHedefi && (
        <OdemeAlPenceresi hedef={odemeHedefi} onKapat={() => setOdemeHedefi(null)} onTamam={() => { setOdemeHedefi(null); setSurum((s) => s + 1); }} />
      )}
    </div>
  );
}
