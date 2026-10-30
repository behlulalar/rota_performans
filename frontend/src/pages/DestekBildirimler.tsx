import { Fragment, useEffect, useState } from "react";
import { destekBildirimleriGetir, topluIptal, topluYenidenDene, type DestekBildirimListesi, type DestekBildirimSatiri, type TopluSonuc } from "../api/destek";
import { DURUM_ETIKET, KANAL_ETIKET, SABLON_ETIKET, type BildirimDurumu, type BildirimSablonu } from "../api/bildirimYonetimi";
import { useOnay } from "../components/OnayPenceresi";
import SayfaBasligi from "../components/SayfaBasligi";
import { hataMesaji } from "../lib/dogrulama";
import { dugme, rozetBasari, rozetHata, rozetNotr, rozetUyari, satir, secimKutusu, td, th } from "../lib/stil";

const BOYUT = 20;
const DURUM_ROZET: Record<BildirimDurumu, string> = {
  bekliyor: rozetUyari, gonderildi: rozetBasari, hata: rozetHata, iptal: rozetNotr,
};

const zaman = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—";
const sablonAdi = (s: string) => SABLON_ETIKET[s as BildirimSablonu] ?? s;

function Detay({ b }: { b: DestekBildirimSatiri }) {
  return (
    <div className="space-y-3 text-[13px]" data-testid="bildirim-detay">
      {b.hata && (
        <div>
          <div className="eyebrow">Hata mesajı</div>
          <p className="mt-1 text-hata break-words">{b.hata}{b.deneme > 0 && ` (${b.deneme}. deneme)`}</p>
        </div>
      )}
      <div>
        <div className="eyebrow">Metin</div>
        <p className="mt-1 text-metin-orta break-words">{b.metin}</p>
      </div>
      <div>
        <div className="eyebrow">Parametreler</div>
        <pre className="num mt-1 overflow-x-auto rounded-[10px] bg-zemin border border-cizgi px-3 py-2 text-xs">{JSON.stringify(b.parametreler ?? {}, null, 2)}</pre>
      </div>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-xs">
        <dt className="text-metin-soluk">Planlı zaman</dt><dd className="num">{zaman(b.planli_zaman)}</dd>
        <dt className="text-metin-soluk">Gönderim</dt><dd className="num">{zaman(b.gonderim_zamani)}</dd>
        <dt className="text-metin-soluk">Öğrenci</dt><dd className="num break-all">{b.ogrenci_id}</dd>
        <dt className="text-metin-soluk">Alıcı iletişim</dt><dd className="num break-all">{b.alici_iletisim_id}</dd>
        {b.yoklama_id && <><dt className="text-metin-soluk">Yoklama</dt><dd className="num break-all">{b.yoklama_id}</dd></>}
        {b.duyuru_id && <><dt className="text-metin-soluk">Duyuru</dt><dd className="num break-all">{b.duyuru_id}</dd></>}
      </dl>
    </div>
  );
}

export default function DestekBildirimler() {
  const onayla = useOnay();
  const [durum, setDurum] = useState("");
  const [kanal, setKanal] = useState("");
  const [sayfa, setSayfa] = useState(1);
  const [veri, setVeri] = useState<DestekBildirimListesi | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<string | null>(null);
  const [islemHatasi, setIslemHatasi] = useState<string | null>(null);
  const [sonuc, setSonuc] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const [surum, setSurum] = useState(0);
  const [acik, setAcik] = useState<number | null>(null);
  const [secili, setSecili] = useState<Set<number>>(new Set());

  useEffect(() => {
    let iptal = false;
    setYukleniyor(true);
    setHata(null);
    destekBildirimleriGetir({ durum, kanal, sayfa, boyut: BOYUT })
      .then((v) => { if (!iptal) { setVeri(v); setAcik(null); setSecili(new Set()); } })
      .catch((e) => !iptal && setHata(hataMesaji(e)))
      .finally(() => !iptal && setYukleniyor(false));
    return () => { iptal = true; };
  }, [durum, kanal, sayfa, surum]);

  async function toplu(tur: "yeniden" | "iptal", ids: number[] | null) {
    const tum = ids === null;
    const adet = tum ? "Tüm hatalı bildirimler" : `${ids.length} bildirim`;
    const tamam = await onayla(
      tur === "yeniden"
        ? { baslik: "Yeniden dene", mesaj: `${adet} yeniden kuyruğa alınacak. Yalnızca hatalı olanlar işlenir.`, onayYazisi: "Yeniden dene" }
        : { baslik: "Bildirimleri iptal et", mesaj: `${adet} iptal edilecek. Bekleyen ve hatalı olanlar gönderilmeyecek.`, onayYazisi: "İptal et", tehlikeli: true },
    );
    if (!tamam) return;
    setMesgul(true);
    setIslemHatasi(null);
    setSonuc(null);
    try {
      const govde = tum ? { tum_hatalilar: true } : { ids };
      const r: TopluSonuc = await (tur === "yeniden" ? topluYenidenDene(govde) : topluIptal(govde));
      setSonuc(`${r.islenen} bildirim işlendi${r.atlanan > 0 ? `, ${r.atlanan} tanesi atlandı (durumu uygun değil)` : ""}.`);
      setSurum((s) => s + 1);
    } catch (e) {
      setIslemHatasi(hataMesaji(e));
    } finally {
      setMesgul(false);
    }
  }

  const sec = (id: number, v: boolean) =>
    setSecili((onceki) => {
      const yeni = new Set(onceki);
      if (v) yeni.add(id); else yeni.delete(id);
      return yeni;
    });

  const kayitlar = veri?.kayitlar ?? [];
  const hepsiSecili = kayitlar.length > 0 && kayitlar.every((b) => secili.has(b.id));
  const hepsiniSec = (v: boolean) => setSecili(v ? new Set(kayitlar.map((b) => b.id)) : new Set());
  const secimIds = [...secili];
  const sayfaSayisi = veri ? Math.max(1, Math.ceil(veri.toplam / veri.boyut)) : 1;

  const rozet = (b: DestekBildirimSatiri) => <span className={DURUM_ROZET[b.durum]}>{DURUM_ETIKET[b.durum]}</span>;
  const kutu = (b: DestekBildirimSatiri) => (
    <input
      type="checkbox" checked={secili.has(b.id)} onChange={(e) => sec(b.id, e.target.checked)}
      aria-label={`${b.id} numaralı bildirimi seç`} className="size-5 accent-[var(--color-altin)]"
    />
  );
  const detayDugmesi = (b: DestekBildirimSatiri) => (
    <button className="text-altin-metin hover:underline min-h-11 px-2" aria-expanded={acik === b.id} onClick={() => setAcik(acik === b.id ? null : b.id)}>
      {acik === b.id ? "Gizle" : "Ayrıntı"}
    </button>
  );

  return (
    <div className="space-y-6">
      <SayfaBasligi
        baslik="Bildirim kuyruğu"
        aciklama="Ham kuyruk kayıtları, hata ayrıntıları ve toplu işlemler"
        eylemler={
          <button className={dugme} disabled={mesgul} onClick={() => void toplu("yeniden", null)}>Tüm hatalıları yeniden dene</button>
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <select value={durum} onChange={(e) => { setDurum(e.target.value); setSayfa(1); }} aria-label="Durum filtresi" className={secimKutusu}>
          <option value="">Tüm durumlar</option>
          {Object.entries(DURUM_ETIKET).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select value={kanal} onChange={(e) => { setKanal(e.target.value); setSayfa(1); }} aria-label="Kanal filtresi" className={secimKutusu}>
          <option value="">Tüm kanallar</option>
          {Object.entries(KANAL_ETIKET).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <div className="flex flex-wrap items-center gap-2 md:ml-auto">
          <span className="num text-[13px] text-metin-soluk" aria-live="polite">{secili.size} seçili</span>
          <button className={dugme} disabled={mesgul || secili.size === 0} onClick={() => void toplu("yeniden", secimIds)}>Seçilenleri yeniden dene</button>
          <button className={dugme} disabled={mesgul || secili.size === 0} onClick={() => void toplu("iptal", secimIds)}>Seçilenleri iptal et</button>
        </div>
      </div>

      {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
      {islemHatasi && <p role="alert" className="text-[13px] text-hata">{islemHatasi}</p>}
      {sonuc && <p role="status" className="text-[13px] text-basari">{sonuc}</p>}
      {!veri ? (
        !hata && <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>
      ) : kayitlar.length === 0 ? (
        <div className="bg-yuzey border border-cizgi rounded-[14px] p-10 text-center text-metin-soluk">Bu filtrede bildirim yok.</div>
      ) : (
        <div className={yukleniyor ? "opacity-60" : ""}>
          <div className="hidden md:block bg-yuzey border border-cizgi rounded-[14px] overflow-hidden">
            <table className="w-full text-[13px]" aria-label="Bildirim kuyruğu">
              <thead><tr>
                <th className={`${th} w-12`}>
                  <input type="checkbox" checked={hepsiSecili} onChange={(e) => hepsiniSec(e.target.checked)} aria-label="Sayfadaki tümünü seç" className="size-5 accent-[var(--color-altin)]" />
                </th>
                <th className={th}>No</th><th className={th}>Oluşturma</th><th className={th}>Tür</th><th className={th}>Kanal</th><th className={th}>Durum</th><th className={th}>Deneme</th><th className={th}></th>
              </tr></thead>
              <tbody>
                {kayitlar.map((b) => (
                  <Fragment key={b.id}>
                    <tr className={satir} data-testid="kuyruk-satiri">
                      <td className="px-4">{kutu(b)}</td>
                      <td className={`${td} num`}>{b.id}</td>
                      <td className={`${td} num whitespace-nowrap`}>{zaman(b.olusturma)}</td>
                      <td className={td}>{sablonAdi(b.sablon)}</td>
                      <td className={td}>{KANAL_ETIKET[b.kanal]}</td>
                      <td className={td}>{rozet(b)}</td>
                      <td className={`${td} num`}>{b.deneme}</td>
                      <td className={`${td} text-right`}>{detayDugmesi(b)}</td>
                    </tr>
                    {acik === b.id && <tr className="border-t border-cizgi bg-yuzey-yuksek"><td colSpan={8} className="px-4 py-3"><Detay b={b} /></td></tr>}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="md:hidden space-y-2">
            {kayitlar.map((b) => (
              <li key={b.id} className="bg-yuzey border border-cizgi rounded-[14px] p-4 space-y-1.5 text-[13px]" data-testid="kuyruk-karti">
                <div className="flex items-center justify-between gap-2">
                  <span className="inline-flex items-center gap-3">{kutu(b)}<span className="num font-medium">#{b.id}</span></span>
                  {rozet(b)}
                </div>
                <div className="num text-xs text-metin-soluk">{zaman(b.olusturma)} · {sablonAdi(b.sablon)} · {KANAL_ETIKET[b.kanal]}</div>
                {b.hata && <div className="text-xs text-hata break-words">Hata: {b.hata}</div>}
                <div>{detayDugmesi(b)}</div>
                {acik === b.id && <Detay b={b} />}
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
    </div>
  );
}
