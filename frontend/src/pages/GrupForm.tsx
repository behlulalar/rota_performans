import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { antrenorleriGetir, type AntrenorOzet } from "../api/antrenor";
import { grupGetir, grupGuncelle, grupOlustur, programGuncelle, type ProgramSlot } from "../api/grup";
import { hataMesaji } from "../lib/dogrulama";
import { dakikaEkle, GUNLER, saat } from "../lib/program";
import Kart from "../components/Kart";
import SayfaBasligi from "../components/SayfaBasligi";
import { birincilDugme, dugme, girdi } from "../lib/stil";

type Satir = { anahtar: number; id?: string; gun: number; baslangic: string; bitis: string };
let sayac = 0;

export default function GrupForm() {
  const { id } = useParams();
  const duzenleme = Boolean(id);
  const git = useNavigate();

  const [ad, setAd] = useState("");
  const [antrenorId, setAntrenorId] = useState("");
  const [kontenjan, setKontenjan] = useState("15");
  const [satirlar, setSatirlar] = useState<Satir[]>([]);
  const [antrenorler, setAntrenorler] = useState<AntrenorOzet[]>([]);
  const [hata, setHata] = useState<string | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [gonderiliyor, setGonderiliyor] = useState(false);

  useEffect(() => {
    let iptal = false;
    (async () => {
      try {
        const aktifler = await antrenorleriGetir(true);
        const g = id ? await grupGetir(id) : null;
        if (iptal) return;
        let liste = aktifler;
        // Pasif bir antrenör atanmışsa seçili kalması için listeye eklenir.
        if (g?.antrenor && !aktifler.some((a) => a.id === g.antrenor!.id)) {
          liste = [...aktifler, { id: g.antrenor.id, ad_soyad: `${g.antrenor.ad_soyad} (pasif)`, telefon: null, aktif: false, giris: null, grup_sayisi: 0, grup_idleri: [], foto_var: g.antrenor.foto_var }];
        }
        setAntrenorler(liste);
        if (g) {
          setAd(g.ad);
          setAntrenorId(g.antrenor?.id ?? "");
          setKontenjan(String(g.kontenjan));
          setSatirlar(g.program.map((s) => ({ anahtar: ++sayac, id: s.id, gun: s.gun, baslangic: saat(s.baslangic), bitis: saat(s.bitis) })));
        }
      } catch (e) {
        if (!iptal) setHata(hataMesaji(e));
      } finally {
        if (!iptal) setYukleniyor(false);
      }
    })();
    return () => {
      iptal = true;
    };
  }, [id]);

  const satirGuncelle = (anahtar: number, d: Partial<Satir>) =>
    setSatirlar((l) => l.map((s) => (s.anahtar === anahtar ? { ...s, ...d } : s)));

  function baslangicDegisti(s: Satir, deger: string) {
    const d: Partial<Satir> = { baslangic: deger };
    if (!s.bitis) {
      const b = dakikaEkle(deger, 90);
      if (b) d.bitis = b;
    }
    satirGuncelle(s.anahtar, d);
  }

  function dogrula(): string | null {
    if (!ad.trim()) return "Grup adı zorunludur.";
    const k = Number(kontenjan);
    if (!Number.isInteger(k) || k < 1) return "Kontenjan en az 1 olan bir tam sayı olmalıdır.";
    const gorulen = new Set<string>();
    for (const s of satirlar) {
      if (!s.baslangic || !s.bitis) return "Program satırlarında başlangıç ve bitiş saati zorunludur.";
      if (s.bitis <= s.baslangic) return `${GUNLER[s.gun - 1]}: bitiş saati başlangıçtan sonra olmalıdır.`;
      const anahtar = `${s.gun}-${s.baslangic}`;
      if (gorulen.has(anahtar)) return `${GUNLER[s.gun - 1]} ${s.baslangic} için program tekrarlanmış.`;
      gorulen.add(anahtar);
    }
    return null;
  }

  async function gonder(e: FormEvent) {
    e.preventDefault();
    const h = dogrula();
    if (h) return setHata(h);
    setHata(null);
    setGonderiliyor(true);
    const program: ProgramSlot[] = satirlar.map((s) => ({ id: s.id, gun: s.gun, baslangic: s.baslangic, bitis: s.bitis }));
    try {
      if (id) {
        await grupGuncelle(id, { ad: ad.trim(), antrenor_id: antrenorId || null, kontenjan: Number(kontenjan) });
        await programGuncelle(id, program);
        git(`/gruplar/${id}`);
      } else {
        const g = await grupOlustur({ ad: ad.trim(), antrenor_id: antrenorId || null, kontenjan: Number(kontenjan), program });
        git(`/gruplar/${g.id}`);
      }
    } catch (err) {
      setHata(hataMesaji(err));
      setGonderiliyor(false);
    }
  }

  if (yukleniyor) return <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>;

  return (
    <form onSubmit={gonder} noValidate className="space-y-4">
      <SayfaBasligi
        baslik={duzenleme ? "Grubu düzenle" : "Yeni grup"}
        aciklama="Ad, antrenör, kontenjan ve haftalık program"
        eylemler={<Link to={id ? `/gruplar/${id}` : "/gruplar"} className={dugme}>Vazgeç</Link>}
      />

      <Kart baslik="Grup bilgileri">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block sm:col-span-2"><span className="text-[13px] text-metin-soluk">Grup adı</span>
            <input className={girdi} value={ad} onChange={(e) => setAd(e.target.value)} /></label>
          <label className="block"><span className="text-[13px] text-metin-soluk">Antrenör</span>
            <select className={girdi} value={antrenorId} onChange={(e) => setAntrenorId(e.target.value)}>
              <option value="">Atanmamış</option>
              {antrenorler.map((a) => <option key={a.id} value={a.id}>{a.ad_soyad}</option>)}
            </select></label>
          <label className="block"><span className="text-[13px] text-metin-soluk">Kontenjan</span>
            <input className={`${girdi} num`} type="number" min={1} inputMode="numeric" value={kontenjan} onChange={(e) => setKontenjan(e.target.value)} /></label>
        </div>
      </Kart>

      <Kart baslik="Haftalık program">
        {satirlar.length === 0 && <p className="text-sm text-metin-soluk mb-3">Henüz program satırı yok.</p>}
        <div className="space-y-3">
          {satirlar.map((s) => (
            <div key={s.anahtar} className="grid grid-cols-2 sm:grid-cols-[1fr_1fr_1fr_auto] gap-2 items-end rounded-[10px] border border-cizgi bg-yuzey-yuksek p-3">
              <label className="block col-span-2 sm:col-span-1"><span className="text-xs text-metin-soluk">Gün</span>
                <select className={girdi} value={s.gun} onChange={(e) => satirGuncelle(s.anahtar, { gun: Number(e.target.value) })}>
                  {GUNLER.map((g, i) => <option key={g} value={i + 1}>{g}</option>)}
                </select></label>
              <label className="block"><span className="text-xs text-metin-soluk">Başlangıç</span>
                <input className={`${girdi} num`} type="time" value={s.baslangic} onChange={(e) => baslangicDegisti(s, e.target.value)} /></label>
              <label className="block"><span className="text-xs text-metin-soluk">Bitiş</span>
                <input className={`${girdi} num`} type="time" value={s.bitis} onChange={(e) => satirGuncelle(s.anahtar, { bitis: e.target.value })} /></label>
              <button type="button" onClick={() => setSatirlar((l) => l.filter((x) => x.anahtar !== s.anahtar))}
                className={`${dugme} col-span-2 sm:col-span-1 text-metin-soluk hover:border-hata hover:text-hata`}>
                Çıkar
              </button>
            </div>
          ))}
        </div>
        <button type="button" onClick={() => setSatirlar((l) => [...l, { anahtar: ++sayac, gun: 1, baslangic: "", bitis: "" }])}
          className={`${dugme} mt-3`}>
          Satır ekle
        </button>
      </Kart>

      {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
      <button type="submit" disabled={gonderiliyor} className={birincilDugme}>
        {gonderiliyor ? "Kaydediliyor…" : "Kaydet"}
      </button>
    </form>
  );
}
