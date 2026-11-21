import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  dersHakkiDuzelt, dersHakkiGetir, ogrenciGetir, telafiPlanlariGetir,
  type DersHakkiDefteri, type HakTur, type OgrenciDetay, type Sayac, type TelafiPlani,
} from "../api/ogrenci";
import { telafiGeriAl } from "../api/takvim";
import { hataMesaji, tarihBicimle } from "../lib/dogrulama";
import { bugun } from "../lib/tarih";
import { birincilDugme, dugme, girdi, rozetBasari, rozetHata, rozetNotr } from "../lib/stil";
import Kart from "./Kart";
import TelafiPlanla, { Pencere, gunMetni, saat } from "./TelafiPlanla";
import { gosterilenDers } from "../lib/dersHakki";
import { useOnay } from "../components/OnayPenceresi";


const TUR_ETIKET: Record<HakTur, string> = {
  paket_yuklemesi: "Paket yüklemesi",
  ders_kullanimi: "Derse katıldı",
  devamsizlik: "Devamsızlık",
  telafi_kullanimi: "Telafi dersine katıldı",
  manuel_duzeltme: "Elle düzeltme",
  iptal: "Düzeltme (geri alındı)",
  telafi_suresi_doldu: "Telafi süresi doldu",
};
const SAYAC_ETIKET: Record<Sayac, string> = { normal: "Kalan ders", telafi: "Telafi" };

function DuzeltmeFormu({ ogrenciId, onKapat, onTamam }: { ogrenciId: string; onKapat: () => void; onTamam: () => void }) {
  const [sayac, setSayac] = useState<Sayac>("normal");
  const [yon, setYon] = useState<"artir" | "azalt">("artir");
  const [sayi, setSayi] = useState("1");
  const [neden, setNeden] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    const n = Number(sayi);
    if (!Number.isInteger(n) || n < 1 || n > 50) return setHata("Miktar 1 ile 50 arasında bir tam sayı olmalıdır.");
    if (neden.trim().length < 3) return setHata("Neden en az 3 karakter olmalıdır.");
    setGonderiliyor(true);
    setHata(null);
    try {
      await dersHakkiDuzelt(ogrenciId, { sayac, miktar: yon === "artir" ? n : -n, neden: neden.trim() });
      onTamam();
    } catch (err) {
      setHata(hataMesaji(err));
      setGonderiliyor(false);
    }
  }

  return (
    <Pencere baslik="Elle düzeltme" onKapat={onKapat}>
      <form onSubmit={gonder} noValidate className="space-y-3">
        <label className="block"><span className="text-sm text-metin-soluk">Sayaç</span>
          <select className={girdi} value={sayac} onChange={(e) => setSayac(e.target.value as Sayac)}>
            <option value="normal">Kalan ders</option>
            <option value="telafi">Telafi</option>
          </select></label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block"><span className="text-sm text-metin-soluk">İşlem</span>
            <select className={girdi} value={yon} onChange={(e) => setYon(e.target.value as "artir" | "azalt")}>
              <option value="artir">Artır</option>
              <option value="azalt">Azalt</option>
            </select></label>
          <label className="block"><span className="text-sm text-metin-soluk">Miktar</span>
            <input className={girdi} type="number" min={1} max={50} value={sayi} onChange={(e) => setSayi(e.target.value)} /></label>
        </div>
        <label className="block"><span className="text-sm text-metin-soluk">Neden</span>
          <input className={girdi} value={neden} onChange={(e) => setNeden(e.target.value)} maxLength={500} /></label>
        <p className="text-xs text-metin-soluk">Düzeltmeler silinemez, kayıt altına alınır.</p>
        {hata && <p role="alert" className="text-sm text-hata">{hata}</p>}
        <button type="submit" disabled={gonderiliyor} className={birincilDugme}>
          {gonderiliyor ? "Kaydediliyor…" : "Düzeltmeyi kaydet"}
        </button>
      </form>
    </Pencere>
  );
}

const YOKLAMA_ROZET = {
  null: { ad: "Bekliyor", sinif: rozetNotr },
  geldi: { ad: "Geldi", sinif: rozetBasari },
  gelmedi: { ad: "Gelmedi", sinif: rozetHata },
} as const;

export default function DersHakki({ ogrenci, onYenile }: { ogrenci: OgrenciDetay; onYenile: (o: OgrenciDetay) => void }) {
  const onayla = useOnay();
  const { id } = ogrenci;
  const h = ogrenci.ders_hakki;
  const [gecmisAcik, setGecmisAcik] = useState(false);
  const [defter, setDefter] = useState<DersHakkiDefteri | null>(null);
  const [planlar, setPlanlar] = useState<TelafiPlani[] | null>(null);
  const [pencere, setPencere] = useState<"duzeltme" | "telafi" | null>(null);
  const [tasinan, setTasinan] = useState<TelafiPlani | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);

  const yukle = useCallback(async () => {
    try {
      const [yeni, p, d] = await Promise.all([ogrenciGetir(id), telafiPlanlariGetir(id), dersHakkiGetir(id)]);
      onYenile(yeni);
      setPlanlar(p);
      setDefter(d);
    } catch (e) {
      setHata(hataMesaji(e));
    }
  }, [id, onYenile]);

  useEffect(() => {
    let iptal = false;
    Promise.all([telafiPlanlariGetir(id), dersHakkiGetir(id)])
      .then(([p, d]) => { if (!iptal) { setPlanlar(p); setDefter(d); } })
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => { iptal = true; };
  }, [id]);

  async function geriAl(p: TelafiPlani) {
    if (!(await onayla({ baslik: "Telafi planını geri al", mesaj: "Telafi planı geri alınsın mı? Telafi hakkı iade edilir.", onayYazisi: "Geri al" }))) return;
    setMesgul(true);
    setHata(null);
    try {
      await telafiGeriAl(p.oturum_id, id);
      await yukle();
    } catch (e) {
      setHata(hataMesaji(e));
    } finally {
      setMesgul(false);
    }
  }

  async function bitti() {
    setPencere(null);
    setTasinan(null);
    setHata(null);
    await yukle();
  }

  const aktif = ogrenci.durum === "aktif";
  const planlanabilir = aktif && h.kullanilabilir_telafi > 0;
  const neden = !aktif ? "Öğrenci pasif olduğu için telafi planlanamaz." : h.kullanilabilir_telafi <= 0 ? "Planlanabilir telafi hakkı yok." : null;
  const fazla = Math.max(0, -h.normal);
  // Süresi dolmamış, kullanılabilir telafi haklarından en yakın son kullanma günü (süresizler sayılmaz).
  const enYakinSon =
    (defter?.hareketler ?? [])
      .filter((x) => x.sayac === "telafi" && x.miktar > 0 && x.son_kullanma && x.son_kullanma >= bugun())
      .map((x) => x.son_kullanma as string)
      .sort()[0] ?? null;

  const hucre = (etiket: string, deger: number) => (
    <div className="bg-yuzey px-6 py-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-metin-soluk">{etiket}</div>
      <div className="num font-display text-[28px] leading-[1.15] mt-1">{gosterilenDers(deger)}</div>
    </div>
  );

  return (
    <Kart baslik="Ders hakkı" bosluksuz>
      <div className="grid grid-cols-1 min-[420px]:grid-cols-3 gap-px bg-cizgi border-y border-cizgi">
        {hucre("Kalan ders", h.normal)}
        {hucre("Telafi", h.telafi)}
        {hucre("Kullanılabilir telafi", h.kullanilabilir_telafi)}
      </div>

      <div className="px-6 py-4 border-b border-cizgi">
        {fazla > 0 && (
          <p role="status" className="mb-3 text-[13px] text-hata">
            Ders hakkı bitti: paketle yüklenenden {fazla} ders fazla işlendi. Yeni paket atanmalı.
          </p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <button className={dugme} disabled={!planlanabilir || mesgul} onClick={() => { setHata(null); setPencere("telafi"); }}>Telafi planla</button>
          <button className={dugme} onClick={() => { setHata(null); setPencere("duzeltme"); }}>Elle düzeltme</button>
          {neden && <span className="text-xs text-metin-soluk">{neden}</span>}
        </div>
        {hata && <p role="alert" className="mt-3 text-[13px] text-hata">{hata}</p>}
      </div>

      <div className="px-6 py-4 border-b border-cizgi">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-metin-soluk mb-2">Planlanan telafiler</h3>
        {planlar === null ? (
          <p className="text-sm text-metin-soluk">Yükleniyor…</p>
        ) : planlar.length === 0 ? (
          <p className="text-sm text-metin-soluk">Planlanmış telafi dersi yok.</p>
        ) : (
          <ul className="divide-y divide-cizgi border-y border-cizgi">
            {planlar.map((p) => {
              const r = YOKLAMA_ROZET[p.yoklama ?? "null"];
              return (
                <li key={p.oturum_id} className="py-2 flex flex-wrap items-center justify-between gap-2 text-sm">
                  <span className="num">{gunMetni(p.tarih)} · {saat(p.baslangic)}–{saat(p.bitis)} · {p.grup.ad}</span>
                  <span className="flex items-center gap-2">
                    <span className={r.sinif}>{r.ad}</span>
                    {p.yoklama === null && p.iptal_edilebilir && <button className={dugme} disabled={mesgul} onClick={() => setTasinan(p)}>Taşı</button>}
                    {p.yoklama === null && <button className={dugme} disabled={mesgul} onClick={() => void geriAl(p)}>Geri al</button>}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="px-6 py-4">
        <button className="text-[13px] font-semibold hover:text-altin-metin min-h-11 md:min-h-0" aria-expanded={gecmisAcik} onClick={() => setGecmisAcik((v) => !v)}>
          {gecmisAcik ? "▾" : "▸"} Hareket geçmişi
        </button>
        {gecmisAcik && (
          <div className="mt-2">
            {defter === null ? (
              <p className="text-sm text-metin-soluk">Yükleniyor…</p>
            ) : defter.hareketler.length === 0 ? (
              <p className="text-sm text-metin-soluk">Henüz hareket yok.</p>
            ) : (
              <ul className="divide-y divide-cizgi border-y border-cizgi">
                {defter.hareketler.map((x) => (
                  <li key={x.id} className="py-2 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium">{TUR_ETIKET[x.tur] ?? x.tur}</span>
                      <span className={`num font-semibold ${x.miktar > 0 ? "text-basari" : "text-hata"}`}>
                        {x.miktar > 0 ? `+${x.miktar}` : `−${Math.abs(x.miktar)}`} <span className="font-normal text-metin-soluk">({SAYAC_ETIKET[x.sayac]})</span>
                      </span>
                    </div>
                    <div className="num text-xs text-metin-soluk">
                      {new Date(x.zaman).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" })}
                      {x.oturum && ` · ${x.oturum.tarih} · ${x.oturum.grup_ad}`}
                    </div>
                    {x.son_kullanma && x.miktar > 0 && (
                      <div className="num text-xs text-metin-soluk">{tarihBicimle(x.son_kullanma)} tarihine kadar geçerli</div>
                    )}
                    {x.neden && <div className="text-xs mt-0.5">{x.neden}</div>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {pencere === "duzeltme" && <DuzeltmeFormu ogrenciId={id} onKapat={() => setPencere(null)} onTamam={() => void bitti()} />}
      {pencere === "telafi" && <TelafiPlanla ogrenciId={id} sonKullanma={enYakinSon} onKapat={() => setPencere(null)} onTamam={() => void bitti()} />}
      {tasinan && <TelafiPlanla ogrenciId={id} sonKullanma={enYakinSon} tasinan={tasinan} onKapat={() => setTasinan(null)} onTamam={() => void bitti()} />}
    </Kart>
  );
}
