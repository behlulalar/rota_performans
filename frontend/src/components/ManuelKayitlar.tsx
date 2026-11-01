import { useEffect, useState, type FormEvent } from "react";
import { manuelKayitEkle, manuelKayitIptal, manuelKayitlariGetir, type ManuelKayit, type ManuelKayitTuru } from "../api/manuelKayit";
import { YONTEM_ETIKET, type OdemeYontemi } from "../api/odeme";
import { hataMesaji, tarihBicimle } from "../lib/dogrulama";
import { paraBicimle } from "../lib/para";
import { birincilDugme, dugme, girdi, hataKutusu, listeSatiri, rozetNotr, secimKutusu } from "../lib/stil";
import { bugun } from "../lib/tarih";
import Kart from "./Kart";

const etiket = "text-[13px] text-metin-soluk";

/** Kayıt formu: tarih varsayılanı seçili ay bu aysa bugün, değilse ayın son günü. */
function KayitFormu({ yil, ay, onEklendi, onKapat }: { yil: number; ay: number; onEklendi: () => void; onKapat: () => void }) {
  const ayinSonu = `${yil}-${String(ay).padStart(2, "0")}-${String(new Date(yil, ay, 0).getDate()).padStart(2, "0")}`;
  const varsayilan = bugun() < ayinSonu ? bugun() : ayinSonu;
  const [tur, setTur] = useState<ManuelKayitTuru>("gelir");
  const [tutar, setTutar] = useState("");
  const [tarih, setTarih] = useState(varsayilan);
  const [yontem, setYontem] = useState<OdemeYontemi>("nakit");
  const [aciklama, setAciklama] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    const n = Number(tutar.replace(/\./g, "").replace(",", "."));
    if (!Number.isFinite(n) || n <= 0) return setHata("Geçerli bir tutar girin.");
    if (aciklama.trim().length < 3) return setHata("Açıklama en az 3 karakter olmalı.");
    if (tarih > bugun()) return setHata("Tarih gelecekte olamaz.");
    setMesgul(true);
    setHata(null);
    try {
      await manuelKayitEkle({ tur, tutar: n.toFixed(2), tarih, yontem, aciklama: aciklama.trim() });
      onEklendi();
    } catch (err) {
      setHata(hataMesaji(err));
    } finally {
      setMesgul(false);
    }
  }

  const secenek = (t: ManuelKayitTuru, ad: string) => (
    <button
      type="button"
      aria-pressed={tur === t}
      onClick={() => setTur(t)}
      className={`flex-1 min-h-10 rounded-[10px] border text-sm font-medium transition-colors ${
        tur === t ? (t === "gelir" ? "border-basari bg-basari-zemin text-basari" : "border-hata bg-hata-zemin text-hata") : "border-cizgi text-metin-soluk hover:bg-yuzey-yuksek"
      }`}
    >
      {ad}
    </button>
  );

  return (
    <form onSubmit={gonder} noValidate className="px-6 pb-5 space-y-4 border-b border-cizgi">
      <div className="flex gap-2 max-w-sm" role="group" aria-label="Kayıt türü">
        {secenek("gelir", "+ Gelir")}
        {secenek("gider", "− Gider")}
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <label className="block"><span className={etiket}>Tutar (₺)</span>
          <input className={girdi} inputMode="decimal" placeholder="0,00" value={tutar} onChange={(e) => setTutar(e.target.value)} /></label>
        <label className="block"><span className={etiket}>Tarih</span>
          <input className={girdi} type="date" max={bugun()} value={tarih} onChange={(e) => setTarih(e.target.value)} /></label>
        <label className="block"><span className={etiket}>Yöntem</span>
          <select className={secimKutusu} value={yontem} onChange={(e) => setYontem(e.target.value as OdemeYontemi)}>
            {(Object.keys(YONTEM_ETIKET) as OdemeYontemi[]).map((y) => <option key={y} value={y}>{YONTEM_ETIKET[y]}</option>)}
          </select></label>
      </div>
      <label className="block"><span className={etiket}>Açıklama</span>
        <input className={girdi} maxLength={200} placeholder={tur === "gelir" ? "Ör. Yaz kampı katılım ücreti" : "Ör. Ekim havuz kirası"} value={aciklama} onChange={(e) => setAciklama(e.target.value)} /></label>
      {hata && <p role="alert" className={hataKutusu}>{hata}</p>}
      <div className="flex gap-2">
        <button type="submit" className={birincilDugme} disabled={mesgul}>{mesgul ? "Kaydediliyor…" : tur === "gelir" ? "Geliri kaydet" : "Gideri kaydet"}</button>
        <button type="button" className={dugme} onClick={onKapat}>Vazgeç</button>
      </div>
    </form>
  );
}

function Satir({ k, gizli, onIptal }: { k: ManuelKayit; gizli: boolean; onIptal: () => void }) {
  const [acik, setAcik] = useState(false);
  const [neden, setNeden] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const gelir = k.tur === "gelir";

  async function iptal(e: FormEvent) {
    e.preventDefault();
    if (neden.trim().length < 3) return setHata("İptal nedeni en az 3 karakter olmalı.");
    setMesgul(true);
    try {
      await manuelKayitIptal(k.id, neden.trim());
      onIptal();
    } catch (err) {
      setHata(hataMesaji(err));
      setMesgul(false);
    }
  }

  return (
    <li className={`${listeSatiri} px-6 py-3`}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <div className={`min-w-0 flex-1 ${k.iptal ? "opacity-60" : ""}`}>
          <div className="text-sm font-medium break-words">{k.aciklama}</div>
          <div className="num text-xs text-metin-soluk">{tarihBicimle(k.tarih)} · {YONTEM_ETIKET[k.yontem]}{k.olusturan ? ` · ${k.olusturan}` : ""}</div>
          {k.iptal && <div className="text-xs text-metin-soluk">İptal: {k.iptal_nedeni}</div>}
        </div>
        <span className={`num text-sm font-semibold ${k.iptal ? "line-through text-metin-soluk" : gelir ? "text-basari" : "text-hata"}`}>
          {gelir ? "+" : "−"}{paraBicimle(k.tutar)}
        </span>
        {k.iptal ? <span className={rozetNotr}>İptal</span> : !gizli && !acik && (
          <button type="button" className={`${dugme} !min-h-9 !px-3`} onClick={() => setAcik(true)}>İptal et</button>
        )}
      </div>
      {acik && (
        <form onSubmit={iptal} noValidate className="mt-3 flex flex-wrap items-end gap-2">
          <label className="block flex-1 min-w-48"><span className={etiket}>İptal nedeni</span>
            <input className={girdi} maxLength={200} value={neden} onChange={(e) => setNeden(e.target.value)} autoFocus /></label>
          <button type="submit" className={dugme} disabled={mesgul}>Kaydı iptal et</button>
          <button type="button" className={dugme} onClick={() => { setAcik(false); setHata(null); }}>Vazgeç</button>
          {hata && <p role="alert" className={`${hataKutusu} w-full`}>{hata}</p>}
        </form>
      )}
    </li>
  );
}

/** Gelir raporu > Manuel gelir ve giderler: seçili ayın kayıtları, ekleme ve iptal. */
export default function ManuelKayitlar({ yil, ay, gizli, onDegisti }: { yil: number; ay: number; gizli: boolean; onDegisti: () => void }) {
  const [kayitlar, setKayitlar] = useState<ManuelKayit[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [formAcik, setFormAcik] = useState(false);
  const [surum, setSurum] = useState(0);

  useEffect(() => {
    let iptal = false;
    manuelKayitlariGetir(yil, ay).then((v) => !iptal && setKayitlar(v), (e) => !iptal && setHata(hataMesaji(e)));
    return () => { iptal = true; };
  }, [yil, ay, surum]);

  const yenile = () => {
    setSurum((n) => n + 1);
    onDegisti();
  };

  return (
    <Kart
      baslik="Manuel gelir ve giderler"
      aciklama="Öğrenci ödemesi dışındaki gelir ve giderler net gelire yansır"
      sag={!gizli && !formAcik && <button type="button" className={birincilDugme} onClick={() => setFormAcik(true)}>Kayıt ekle</button>}
      bosluksuz
    >
      {formAcik && <KayitFormu yil={yil} ay={ay} onKapat={() => setFormAcik(false)} onEklendi={() => { setFormAcik(false); yenile(); }} />}
      {hata && <p role="alert" className={`${hataKutusu} mx-6 mb-4`}>{hata}</p>}
      {kayitlar?.length === 0 && !formAcik && <p className="px-6 pb-6 text-sm text-metin-soluk">Bu ay manuel kayıt yok.</p>}
      {!!kayitlar?.length && <ul>{kayitlar.map((k) => <Satir key={k.id} k={k} gizli={gizli} onIptal={yenile} />)}</ul>}
    </Kart>
  );
}
