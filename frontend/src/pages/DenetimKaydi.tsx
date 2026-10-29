import { Fragment, useEffect, useState } from "react";
import { denetimGetir, denetimIslemleriGetir, islemEtiketi, type DenetimListesi, type DenetimSatiri } from "../api/denetim";
import SayfaBasligi from "../components/SayfaBasligi";
import { hataMesaji } from "../lib/dogrulama";
import { dugme, girdi, rozetNotr, satir, secimKutusu, td, th } from "../lib/stil";

const BOYUT = 50;

const zamanBicimle = (iso: string) =>
  new Date(iso).toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" });

const kullaniciAdi = (s: DenetimSatiri) => (s.kullanici ? s.kullanici.ad_soyad || s.kullanici.giris : "Sistem / bilinmiyor");
const hedefMetni = (s: DenetimSatiri) => [s.hedef_tur, s.hedef_id].filter(Boolean).join(" · ") || "—";
const degerMetni = (v: unknown) => (typeof v === "object" && v !== null ? JSON.stringify(v) : String(v));

function Detay({ detay }: { detay?: Record<string, unknown> | null }) {
  const girisler = Object.entries(detay ?? {});
  if (girisler.length === 0) return <p className="text-[13px] text-metin-soluk">Ek ayrıntı yok.</p>;
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-[13px]">
      {girisler.map(([k, v]) => (
        <Fragment key={k}><dt className="text-metin-soluk">{k}</dt><dd className="num break-all">{degerMetni(v)}</dd></Fragment>
      ))}
    </dl>
  );
}

export default function DenetimKaydi() {
  const [islem, setIslem] = useState("");
  const [baslangic, setBaslangic] = useState("");
  const [bitis, setBitis] = useState("");
  const [arama, setArama] = useState("");
  const [ara, setAra] = useState("");
  const [sayfa, setSayfa] = useState(1);
  const [islemler, setIslemler] = useState<string[]>([]);
  const [veri, setVeri] = useState<DenetimListesi | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [yukleniyor, setYukleniyor] = useState(false);
  const [acik, setAcik] = useState<number | null>(null);

  useEffect(() => {
    denetimIslemleriGetir().then(setIslemler).catch(() => setIslemler([]));
  }, []);

  // Arama kutusu: yazmayı bitirince sorgulanır.
  useEffect(() => {
    const t = setTimeout(() => { setAra(arama.trim()); setSayfa(1); }, 300);
    return () => clearTimeout(t);
  }, [arama]);

  useEffect(() => {
    let iptal = false;
    setYukleniyor(true);
    denetimGetir({ islem: islem || undefined, baslangic: baslangic || undefined, bitis: bitis || undefined, ara: ara || undefined, sayfa, boyut: BOYUT })
      .then((v) => { if (!iptal) { setVeri(v); setHata(null); setAcik(null); } })
      .catch((e) => !iptal && setHata(hataMesaji(e)))
      .finally(() => !iptal && setYukleniyor(false));
    return () => { iptal = true; };
  }, [islem, baslangic, bitis, ara, sayfa]);

  const sayfaSayisi = veri ? Math.max(1, Math.ceil(veri.toplam / veri.boyut)) : 1;
  const ilk = veri && veri.toplam > 0 ? (veri.sayfa - 1) * veri.boyut + 1 : 0;
  const son = veri ? Math.min(veri.toplam, (veri.sayfa - 1) * veri.boyut + veri.items.length) : 0;
  const islemSecenekleri = islem && !islemler.includes(islem) ? [...islemler, islem] : islemler;

  return (
    <div className="space-y-6">
      <SayfaBasligi baslik="Denetim kaydı" aciklama="Kim, ne zaman, hangi işlemi yaptı. Kayıtlar yalnızca okunur; kişisel veri ve şifre tutulmaz." />

      <div className="flex flex-wrap items-end gap-3">
        <label className="block"><span className="text-xs text-metin-soluk">İşlem</span>
          <select value={islem} onChange={(e) => { setIslem(e.target.value); setSayfa(1); }} aria-label="İşlem filtresi" className={`${secimKutusu} mt-0.5 block`}>
            <option value="">Tüm işlemler</option>
            {islemSecenekleri.map((i) => <option key={i} value={i}>{islemEtiketi(i)}</option>)}
          </select></label>
        <label className="block"><span className="text-xs text-metin-soluk">Başlangıç</span>
          <input type="date" className={`${girdi} mt-0.5`} value={baslangic} max={bitis || undefined} onChange={(e) => { setBaslangic(e.target.value); setSayfa(1); }} aria-label="Başlangıç tarihi" /></label>
        <label className="block"><span className="text-xs text-metin-soluk">Bitiş</span>
          <input type="date" className={`${girdi} mt-0.5`} value={bitis} min={baslangic || undefined} onChange={(e) => { setBitis(e.target.value); setSayfa(1); }} aria-label="Bitiş tarihi" /></label>
        <input type="search" value={arama} onChange={(e) => setArama(e.target.value)} placeholder="Kullanıcı veya hedef ara…" aria-label="Ara" className={`${secimKutusu} flex-1 min-w-48 max-w-sm`} />
      </div>

      {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
      {!veri ? (
        !hata && <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>
      ) : veri.items.length === 0 ? (
        <div className="bg-yuzey border border-cizgi rounded-[14px] p-10 text-center text-metin-soluk">Bu filtreyle denetim kaydı yok.</div>
      ) : (
        <div className={yukleniyor ? "opacity-60" : ""}>
          <div className="hidden md:block bg-yuzey border border-cizgi rounded-[14px] overflow-hidden">
            <table className="w-full text-[13px]" aria-label="Denetim kaydı">
              <thead><tr>
                <th className={th}>Zaman</th><th className={th}>Kullanıcı</th><th className={th}>İşlem</th><th className={th}>Hedef</th><th className={th}>IP</th><th className={th}></th>
              </tr></thead>
              <tbody>
                {veri.items.map((s) => (
                  <Fragment key={s.id}>
                    <tr className={satir} data-testid="denetim-satiri">
                      <td className={`${td} num whitespace-nowrap`}>{zamanBicimle(s.zaman)}</td>
                      <td className={td}>{kullaniciAdi(s)}{s.kullanici && <div className="text-xs text-metin-soluk">{s.kullanici.giris}</div>}</td>
                      <td className={td}><span className={rozetNotr}>{islemEtiketi(s.islem)}</span></td>
                      <td className={`${td} num break-all`}>{hedefMetni(s)}</td>
                      <td className={`${td} num`}>{s.ip ?? "—"}</td>
                      <td className={`${td} text-right`}>
                        <button className="text-altin-metin hover:underline min-h-11 px-2" aria-expanded={acik === s.id} onClick={() => setAcik(acik === s.id ? null : s.id)}>
                          {acik === s.id ? "Gizle" : "Ayrıntı"}
                        </button>
                      </td>
                    </tr>
                    {acik === s.id && <tr className="border-t border-cizgi bg-yuzey-yuksek"><td colSpan={6} className="px-4 py-3"><Detay detay={s.detay} /></td></tr>}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="md:hidden space-y-3">
            {veri.items.map((s) => (
              <li key={s.id} className="bg-yuzey border border-cizgi rounded-[14px] p-4 space-y-1.5 text-[13px]" data-testid="denetim-karti">
                <div className="flex items-start justify-between gap-2">
                  <span className={rozetNotr}>{islemEtiketi(s.islem)}</span>
                  <span className="num text-xs text-metin-soluk text-right">{zamanBicimle(s.zaman)}</span>
                </div>
                <div className="font-medium">{kullaniciAdi(s)}</div>
                <div className="num text-metin-soluk break-all">Hedef: {hedefMetni(s)}</div>
                <div className="num text-metin-soluk">IP: {s.ip ?? "—"}</div>
                <button className="text-altin-metin hover:underline min-h-11" aria-expanded={acik === s.id} onClick={() => setAcik(acik === s.id ? null : s.id)}>
                  {acik === s.id ? "Gizle" : "Ayrıntı"}
                </button>
                {acik === s.id && <Detay detay={s.detay} />}
              </li>
            ))}
          </ul>

          <div className="flex items-center justify-between gap-3 mt-4">
            <span className="num text-[13px] text-metin-soluk" aria-live="polite">{ilk}–{son} / {veri.toplam}</span>
            <div className="flex gap-2">
              <button className={dugme} disabled={sayfa <= 1 || yukleniyor} onClick={() => setSayfa(sayfa - 1)}>Önceki</button>
              <button className={dugme} disabled={sayfa >= sayfaSayisi || yukleniyor} onClick={() => setSayfa(sayfa + 1)}>Sonraki</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
