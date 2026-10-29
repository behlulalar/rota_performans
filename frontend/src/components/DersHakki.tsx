import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  dersHakkiDuzelt, dersHakkiGetir, ogrenciGetir, telafiAdaylariGetir, telafiPlanlariGetir,
  type DersHakkiDefteri, type HakTur, type OgrenciDetay, type Sayac, type TelafiAdayi, type TelafiPlani,
} from "../api/ogrenci";
import { telafiGeriAl, telafiPlanla } from "../api/takvim";
import { hataMesaji } from "../lib/dogrulama";
import { bugun, gunEkle, tarihCoz, yyyyAyGun } from "../lib/tarih";
import { birincilDugme, dugme, girdi, rozetBasari, rozetHata, rozetNotr } from "../lib/stil";
import Kart from "./Kart";
import { useOnay } from "../components/OnayPenceresi";


const TUR_ETIKET: Record<HakTur, string> = {
  paket_yuklemesi: "Paket yüklemesi",
  ders_kullanimi: "Derse katıldı",
  devamsizlik: "Devamsızlık",
  telafi_kullanimi: "Telafi dersine katıldı",
  manuel_duzeltme: "Elle düzeltme",
  iptal: "Düzeltme (geri alındı)",
};
const SAYAC_ETIKET: Record<Sayac, string> = { normal: "Kalan ders", telafi: "Telafi" };

const gunMetni = (s: string) => tarihCoz(s).toLocaleDateString("tr-TR", { day: "numeric", month: "long", weekday: "long" });
const saat = (s: string) => s.slice(0, 5);

function Pencere({ baslik, onKapat, children }: { baslik: string; onKapat: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-30 bg-black/70 grid place-items-center p-4" role="dialog" aria-modal="true" aria-label={baslik}>
      <div className="w-full max-w-md max-h-full overflow-y-auto bg-yuzey border border-cizgi-guclu rounded-[14px]">
        <div className="flex items-center justify-between px-4 min-h-11 border-b border-cizgi">
          <h2 className="font-display text-[19px] leading-6">{baslik}</h2>
          <button onClick={onKapat} className="px-2 min-h-11 text-[13px] text-metin-soluk hover:text-metin" aria-label="Kapat">Kapat</button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}

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

function TelafiPenceresi({ ogrenciId, onKapat, onTamam }: { ogrenciId: string; onKapat: () => void; onTamam: () => void }) {
  const [adaylar, setAdaylar] = useState<TelafiAdayi[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);

  useEffect(() => {
    let iptal = false;
    const b = new Date();
    telafiAdaylariGetir(ogrenciId, bugun(), yyyyAyGun(gunEkle(b, 14)))
      .then((v) => !iptal && setAdaylar(v))
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => { iptal = true; };
  }, [ogrenciId]);

  async function sec(a: TelafiAdayi) {
    setMesgul(true);
    setHata(null);
    try {
      await telafiPlanla(a.oturum.id, ogrenciId);
      onTamam();
    } catch (err) {
      setHata(hataMesaji(err));
      setMesgul(false);
    }
  }

  return (
    <Pencere baslik="Telafi planla" onKapat={onKapat}>
      {hata && <p role="alert" className="mb-3 text-sm text-hata">{hata}</p>}
      {adaylar === null ? (
        !hata && <p className="text-sm text-metin-soluk">Yükleniyor…</p>
      ) : adaylar.length === 0 ? (
        <p className="text-sm text-metin-soluk">Önümüzdeki 14 günde uygun ders yok</p>
      ) : (
        <ul className="space-y-2">
          {adaylar.map((a) => (
            <li key={a.oturum.id} className="rounded-[10px] border border-cizgi px-3 py-2.5 flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm min-w-0">
                <div className="font-medium">{gunMetni(a.oturum.tarih)} · {saat(a.oturum.baslangic)}–{saat(a.oturum.bitis)}</div>
                <div className="text-metin-soluk">
                  {a.oturum.grup.ad}{a.oturum.antrenor ? ` · ${a.oturum.antrenor.ad_soyad}` : ""} · {a.bos_yer} boş yer
                </div>
              </div>
              <button className={dugme} disabled={mesgul} aria-label={`Seç: ${a.oturum.grup.ad} ${a.oturum.tarih}`} onClick={() => void sec(a)}>Seç</button>
            </li>
          ))}
        </ul>
      )}
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
    setHata(null);
    await yukle();
  }

  const aktif = ogrenci.durum === "aktif";
  const planlanabilir = aktif && h.kullanilabilir_telafi > 0;
  const neden = !aktif ? "Öğrenci pasif olduğu için telafi planlanamaz." : h.kullanilabilir_telafi <= 0 ? "Planlanabilir telafi hakkı yok." : null;
  const sayi = (n: number) => (n < 0 ? "text-hata" : "");

  const hucre = (etiket: string, deger: number) => (
    <div className="bg-yuzey px-6 py-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-metin-soluk">{etiket}</div>
      <div className={`num font-display text-[28px] leading-[1.15] mt-1 ${sayi(deger)}`}>{deger}</div>
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
        {(h.normal < 0 || h.telafi < 0) && <p className="mb-3 text-[13px] text-hata">Paket yüklemesi bekleniyor</p>}
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
                    {x.neden && <div className="text-xs mt-0.5">{x.neden}</div>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {pencere === "duzeltme" && <DuzeltmeFormu ogrenciId={id} onKapat={() => setPencere(null)} onTamam={() => void bitti()} />}
      {pencere === "telafi" && <TelafiPenceresi ogrenciId={id} onKapat={() => setPencere(null)} onTamam={() => void bitti()} />}
    </Kart>
  );
}
