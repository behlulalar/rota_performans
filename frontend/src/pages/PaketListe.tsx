import { useEffect, useState, type FormEvent } from "react";
import { paketGuncelle, paketleriGetir, paketOlustur, TUR_ETIKET, type Paket, type PaketTur } from "../api/paket";
import Modal from "../components/Modal";
import SayfaBasligi from "../components/SayfaBasligi";
import { hataMesaji } from "../lib/dogrulama";
import { paraBicimle } from "../lib/para";
import { birincilDugme, dugme, girdi, rozetBasari, rozetNotr, satir, secimKutusu, td, th } from "../lib/stil";

const VARSAYILAN_AY: Record<PaketTur, number> = { aylik: 1, uc_aylik: 3, alti_aylik: 6, yillik: 12, ozel_ders: 1 };
const FIYAT_DESENI = /^\d+([.,]\d{1,2})?$/;
const fiyatNormal = (s: string) => s.trim().replace(",", ".");

function Sure({ p }: { p: Paket }) {
  return <>{p.sure_ay} ay</>;
}

function YeniPaket({ onKapat, onTamam }: { onKapat: () => void; onTamam: () => void }) {
  const [ad, setAd] = useState("");
  const [tur, setTur] = useState<PaketTur>("aylik");
  const [ders, setDers] = useState("8");
  const [ay, setAy] = useState("1");
  const [fiyat, setFiyat] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    const d = Number(ders);
    const a = Number(ay);
    if (ad.trim().length < 2) return setHata("Paket adı en az 2 karakter olmalı.");
    if (!Number.isInteger(d) || d < 1) return setHata("Ders sayısı 1 veya daha büyük bir tam sayı olmalı.");
    if (!Number.isInteger(a) || a < 1) return setHata("Süre en az 1 ay olmalı.");
    if (!FIYAT_DESENI.test(fiyatNormal(fiyat))) return setHata("Geçerli bir fiyat girin (ör. 3400 veya 3400,50).");
    setMesgul(true);
    setHata(null);
    try {
      await paketOlustur({ ad: ad.trim(), tur, ders_sayisi: d, sure_ay: a, varsayilan_fiyat: fiyatNormal(fiyat) });
      onTamam();
    } catch (err) {
      setHata(hataMesaji(err));
      setMesgul(false);
    }
  }

  return (
    <Modal baslik="Yeni paket" onKapat={onKapat}>
      <form onSubmit={gonder} noValidate className="space-y-3">
        <label className="block"><span className="text-sm text-metin-soluk">Paket adı</span>
          <input className={girdi} value={ad} onChange={(e) => setAd(e.target.value)} autoFocus /></label>
        <label className="block"><span className="text-sm text-metin-soluk">Tür</span>
          <select
            className={`${girdi} bg-zemin`}
            value={tur}
            onChange={(e) => {
              const t = e.target.value as PaketTur;
              setTur(t);
              setAy(String(VARSAYILAN_AY[t]));
            }}
          >
            {(Object.keys(TUR_ETIKET) as PaketTur[]).map((t) => <option key={t} value={t}>{TUR_ETIKET[t]}</option>)}
          </select></label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block"><span className="text-sm text-metin-soluk">Ders sayısı</span>
            <input className={girdi} type="number" min={1} inputMode="numeric" value={ders} onChange={(e) => setDers(e.target.value)} /></label>
          <label className="block"><span className="text-sm text-metin-soluk">Süre (ay)</span>
            <input className={girdi} type="number" min={1} inputMode="numeric" value={ay} onChange={(e) => setAy(e.target.value)} /></label>
        </div>
        <label className="block"><span className="text-sm text-metin-soluk">Varsayılan fiyat (₺)</span>
          <input className={girdi} inputMode="decimal" value={fiyat} onChange={(e) => setFiyat(e.target.value)} placeholder="3400" /></label>
        {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
        <button type="submit" disabled={mesgul} className={birincilDugme}>{mesgul ? "Kaydediliyor…" : "Paketi oluştur"}</button>
      </form>
    </Modal>
  );
}

function PaketDuzenle({ paket, onKapat, onTamam }: { paket: Paket; onKapat: () => void; onTamam: () => void }) {
  const [ad, setAd] = useState(paket.ad);
  const [fiyat, setFiyat] = useState(String(Number(paket.varsayilan_fiyat)).replace(".", ","));
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    if (ad.trim().length < 2) return setHata("Paket adı en az 2 karakter olmalı.");
    if (!FIYAT_DESENI.test(fiyatNormal(fiyat))) return setHata("Geçerli bir fiyat girin (ör. 3400 veya 3400,50).");
    setMesgul(true);
    setHata(null);
    try {
      await paketGuncelle(paket.id, { ad: ad.trim(), varsayilan_fiyat: fiyatNormal(fiyat) });
      onTamam();
    } catch (err) {
      setHata(hataMesaji(err));
      setMesgul(false);
    }
  }

  return (
    <Modal baslik="Paketi düzenle" onKapat={onKapat}>
      <form onSubmit={gonder} noValidate className="space-y-3">
        <p className="text-sm text-metin-soluk">Tür, ders sayısı ve süre sonradan değiştirilemez. Fiyat değişikliği yalnız yeni atamaları etkiler.</p>
        <label className="block"><span className="text-sm text-metin-soluk">Paket adı</span>
          <input className={girdi} value={ad} onChange={(e) => setAd(e.target.value)} autoFocus /></label>
        <label className="block"><span className="text-sm text-metin-soluk">Varsayılan fiyat (₺)</span>
          <input className={girdi} inputMode="decimal" value={fiyat} onChange={(e) => setFiyat(e.target.value)} /></label>
        {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
        <button type="submit" disabled={mesgul} className={birincilDugme}>{mesgul ? "Kaydediliyor…" : "Kaydet"}</button>
      </form>
    </Modal>
  );
}

export default function PaketListe() {
  const [filtre, setFiltre] = useState("tum");
  const [liste, setListe] = useState<Paket[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [surum, setSurum] = useState(0);
  const [yeni, setYeni] = useState(false);
  const [duzenlenen, setDuzenlenen] = useState<Paket | null>(null);
  const [mesgul, setMesgul] = useState(false);

  useEffect(() => {
    let iptal = false;
    paketleriGetir()
      .then((v) => { if (!iptal) { setListe(v); setHata(null); } })
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => {
      iptal = true;
    };
  }, [surum]);

  const yenile = () => setSurum((s) => s + 1);

  async function durumDegistir(p: Paket) {
    setMesgul(true);
    setHata(null);
    try {
      await paketGuncelle(p.id, { aktif: !p.aktif });
      yenile();
    } catch (e) {
      setHata(hataMesaji(e));
    } finally {
      setMesgul(false);
    }
  }

  const gorunen = (liste ?? []).filter((p) => filtre === "tum" || (filtre === "aktif" ? p.aktif : !p.aktif));
  const rozet = (p: Paket) => <span className={p.aktif ? rozetBasari : rozetNotr}>{p.aktif ? "Aktif" : "Pasif"}</span>;
  const eylemler = (p: Paket) => (
    <div className="flex flex-wrap gap-2">
      <button className={dugme} onClick={() => setDuzenlenen(p)} aria-label={`${p.ad} düzenle`}>Düzenle</button>
      <button className={dugme} disabled={mesgul} onClick={() => void durumDegistir(p)} aria-label={`${p.ad} ${p.aktif ? "pasife al" : "aktif et"}`}>
        {p.aktif ? "Pasife al" : "Aktif et"}
      </button>
    </div>
  );

  return (
    <div>
      <SayfaBasligi
        baslik="Paketler"
        aciklama={liste ? `${liste.length} paket tanımı · ders sayısı, süre ve varsayılan fiyat` : "Paket tanımları ve varsayılan fiyatlar"}
        eylemler={<button className={birincilDugme} onClick={() => setYeni(true)}>Yeni paket</button>}
      />
      <div className="mb-4">
        <select value={filtre} onChange={(e) => setFiltre(e.target.value)} aria-label="Durum filtresi" className={secimKutusu}>
          <option value="tum">Tüm paketler</option>
          <option value="aktif">Aktif</option>
          <option value="pasif">Pasif</option>
        </select>
      </div>
      {hata && <p role="alert" className="text-[13px] text-hata mb-3">{hata}</p>}
      {!liste ? (
        !hata && <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>
      ) : gorunen.length === 0 ? (
        <div className="bg-yuzey border border-cizgi rounded-[14px] p-10 text-center text-metin-soluk">
          {liste.length === 0 ? "Henüz paket tanımlanmamış. \"Yeni paket\" ile başlayın." : "Bu filtreye uyan paket yok."}
        </div>
      ) : (
        <>
          <div className="hidden md:block bg-yuzey border border-cizgi rounded-[14px] overflow-hidden">
            <table className="w-full text-[13px]">
              <thead>
                <tr>
                  <th className={th}>Paket</th>
                  <th className={th}>Tür</th>
                  <th className={th}>Ders</th>
                  <th className={th}>Süre</th>
                  <th className={th}>Fiyat</th>
                  <th className={th}>Durum</th>
                  <th className={th}></th>
                </tr>
              </thead>
              <tbody>
                {gorunen.map((p) => (
                  <tr key={p.id} className={satir}>
                    <td className={`${td} font-medium`}>{p.ad}</td>
                    <td className={`${td} text-metin-orta`}>{TUR_ETIKET[p.tur]}</td>
                    <td className={`${td} num`}>{p.ders_sayisi}</td>
                    <td className={`${td} num`}><Sure p={p} /></td>
                    <td className={`${td} num`}>{paraBicimle(p.varsayilan_fiyat)}</td>
                    <td className={td}>{rozet(p)}</td>
                    <td className={`${td} text-right`}><div className="flex justify-end">{eylemler(p)}</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="md:hidden space-y-2">
            {gorunen.map((p) => (
              <li key={p.id} className="bg-yuzey border border-cizgi rounded-[14px] p-4 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium">{p.ad}</span>
                  {rozet(p)}
                </div>
                <div className="text-[13px] text-metin-soluk">{TUR_ETIKET[p.tur]} · {p.ders_sayisi} ders · <Sure p={p} /></div>
                <div className="num font-medium">{paraBicimle(p.varsayilan_fiyat)}</div>
                {eylemler(p)}
              </li>
            ))}
          </ul>
        </>
      )}
      {yeni && <YeniPaket onKapat={() => setYeni(false)} onTamam={() => { setYeni(false); yenile(); }} />}
      {duzenlenen && <PaketDuzenle paket={duzenlenen} onKapat={() => setDuzenlenen(null)} onTamam={() => { setDuzenlenen(null); yenile(); }} />}
    </div>
  );
}
