import { useEffect, useState, type FormEvent } from "react";
import {
  DURUM_ETIKET, ogrenciPaketiniIptalEt, ogrenciPaketleriniGetir, paketAta, paketleriGetir,
  type OgrenciPaketi, type Paket, type PaketDurum,
} from "../api/paket";
import { odemeIptalEt, YONTEM_ETIKET } from "../api/odeme";
import { hataMesaji, tarihBicimle } from "../lib/dogrulama";
import { paraBicimle } from "../lib/para";
import { bugun } from "../lib/tarih";
import { birincilDugme, dugme, girdi, rozetBasari, rozetBirincil, rozetHata, rozetNotr, rozetUyari, uyariKutusu } from "../lib/stil";
import FinansNotu, { useTutarGizli } from "./FinansNotu";
import Kart from "./Kart";
import Modal from "./Modal";
import OdemeAlPenceresi from "./OdemeAlPenceresi";
import { useOnay } from "../components/OnayPenceresi";

const DURUM_ROZET: Record<PaketDurum, string> = {
  odeme_bekliyor: rozetUyari,
  odendi: rozetBasari,
  iptal: rozetNotr,
};
// Öğrenci sayfasında varsayılan olarak en yeni paketler görünür.
const ILK_GORUNEN = 3;
const FIYAT_DESENI = /^\d+([.,]\d{1,2})?$/;

function AtamaPenceresi({ ogrenciId, paketler, onKapat, onTamam }: { ogrenciId: string; paketler: Paket[]; onKapat: () => void; onTamam: () => void }) {
  const [paketId, setPaketId] = useState(paketler[0]?.id ?? "");
  const [baslangic, setBaslangic] = useState(bugun());
  const [ozel, setOzel] = useState(false);
  const [tutar, setTutar] = useState("");
  const [neden, setNeden] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const secili = paketler.find((p) => p.id === paketId);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    if (!secili) return setHata("Paket seçin.");
    if (!baslangic) return setHata("Başlangıç tarihi seçin.");
    const govde = { paket_id: secili.id, baslangic } as Parameters<typeof paketAta>[1];
    if (ozel) {
      const t = tutar.trim().replace(",", ".");
      if (!FIYAT_DESENI.test(t)) return setHata("Geçerli bir özel fiyat girin (ör. 3000 veya 3000,50).");
      const n = neden.trim();
      if (n.length < 3 || n.length > 200) return setHata("Özel fiyat nedeni 3 ile 200 karakter arasında olmalı.");
      govde.ozel_fiyat = t;
      govde.ozel_fiyat_nedeni = n;
    }
    setMesgul(true);
    setHata(null);
    try {
      await paketAta(ogrenciId, govde);
      onTamam();
    } catch (err) {
      setHata(hataMesaji(err));
      setMesgul(false);
    }
  }

  return (
    <Modal baslik="Paket ata" onKapat={onKapat}>
      <form onSubmit={gonder} noValidate className="space-y-3">
        <label className="block"><span className="text-sm text-metin-soluk">Paket</span>
          <select className={`${girdi} bg-zemin`} value={paketId} onChange={(e) => setPaketId(e.target.value)}>
            {paketler.map((p) => <option key={p.id} value={p.id}>{p.ad}</option>)}
          </select></label>
        {secili && (
          <p className="text-sm text-metin-soluk">
            {secili.ders_sayisi} ders · {secili.sure_ay} ay · Liste fiyatı <span className="num text-metin font-medium">{paraBicimle(secili.varsayilan_fiyat)}</span>
          </p>
        )}
        {secili?.aciklama && <p className="rounded-[10px] bg-yuzey-yuksek px-3 py-2 text-[13px] text-metin-orta whitespace-pre-line break-words">{secili.aciklama}</p>}
        <label className="block"><span className="text-sm text-metin-soluk">Başlangıç tarihi</span>
          <input className={girdi} type="date" value={baslangic} onChange={(e) => setBaslangic(e.target.value)} /></label>
        <label className="flex items-center gap-2 min-h-11 text-sm">
          <input type="checkbox" checked={ozel} onChange={(e) => setOzel(e.target.checked)} className="size-4" />
          Özel fiyat uygula
        </label>
        {ozel && (
          <>
            <label className="block"><span className="text-sm text-metin-soluk">Özel fiyat (₺)</span>
              <input className={girdi} inputMode="decimal" value={tutar} onChange={(e) => setTutar(e.target.value)} /></label>
            <label className="block"><span className="text-sm text-metin-soluk">Özel fiyat nedeni</span>
              <input className={girdi} value={neden} onChange={(e) => setNeden(e.target.value)} maxLength={200} /></label>
          </>
        )}
        {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
        <button type="submit" disabled={mesgul || !secili} className={birincilDugme}>{mesgul ? "Kaydediliyor…" : "Paketi ata"}</button>
      </form>
    </Modal>
  );
}

function GeriAlPenceresi({ odemeId, onKapat, onTamam }: { odemeId: string; onKapat: () => void; onTamam: () => void }) {
  const [neden, setNeden] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    const n = neden.trim();
    if (n.length < 3 || n.length > 200) return setHata("Geri alma nedeni 3 ile 200 karakter arasında olmalı.");
    setMesgul(true);
    setHata(null);
    try {
      await odemeIptalEt(odemeId, n);
      onTamam();
    } catch (err) {
      setHata(hataMesaji(err));
      setMesgul(false);
    }
  }

  return (
    <Modal baslik="Ödemeyi geri al" onKapat={onKapat}>
      <form onSubmit={gonder} noValidate className="space-y-3">
        <p className={uyariKutusu}>
          Ödeme geri alınınca bu ödemeyle yüklenen ders hakkı da geri alınır ve paket yeniden "Ödeme bekliyor" olur.
          Dersler bu arada kullanıldıysa kalan ders 0'a iner ve fazla işlenen dersler için "Ders hakkı bitti" notu görünür.
        </p>
        <label className="block"><span className="text-sm text-metin-soluk">Geri alma nedeni</span>
          <input className={girdi} value={neden} onChange={(e) => setNeden(e.target.value)} maxLength={200} autoFocus /></label>
        {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
        <button type="submit" disabled={mesgul} className={birincilDugme}>{mesgul ? "Geri alınıyor…" : "Ödemeyi geri al"}</button>
      </form>
    </Modal>
  );
}

function Satir({ ad, children }: { ad: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2 border-t border-cizgi first:border-t-0 text-sm">
      <dt className="text-metin-soluk shrink-0">{ad}</dt>
      <dd className="num text-right min-w-0">{children}</dd>
    </div>
  );
}

/** Tek paketin ayrıntıları liste olarak: dönem, fiyatlar, ödemeler ve işlemler. */
function PaketDetayPenceresi({
  p, mesgul, onKapat, onOdemeAl, onIptal, onGeriAl,
}: {
  p: OgrenciPaketi;
  mesgul: boolean;
  onKapat: () => void;
  onOdemeAl: () => void;
  onIptal: () => void;
  onGeriAl: (odemeId: string) => void;
}) {
  const gizli = useTutarGizli();
  const odemeler = p.odemeler ?? [];
  const kalan = Math.max(0, Number(p.uygulanan_fiyat) - Number(p.toplam_odenen));
  const iptalEdilebilir = !gizli && p.durum === "odeme_bekliyor" && Number(p.toplam_odenen) === 0;
  return (
    <Modal baslik="Paket detayı" onKapat={onKapat}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-display text-[20px] leading-6">{p.paket_adi}</h3>
          <span className={DURUM_ROZET[p.durum]}>{DURUM_ETIKET[p.durum]}</span>
          {p.fiyat_ozel_mi && <span className={rozetBirincil}>Özel fiyat</span>}
        </div>

        <dl>
          <Satir ad="Ders sayısı">{p.ders_sayisi}</Satir>
          <Satir ad="Dönem">{p.baslangic && p.bitis ? `${tarihBicimle(p.baslangic)} – ${tarihBicimle(p.bitis)}` : "Belirsiz"}</Satir>
          <Satir ad="Liste fiyatı">{paraBicimle(p.liste_fiyati)}</Satir>
          {p.fiyat_ozel_mi && <Satir ad="Uygulanan fiyat">{paraBicimle(p.uygulanan_fiyat)}</Satir>}
          <Satir ad="Ödenen">{paraBicimle(p.toplam_odenen)}</Satir>
          {p.durum !== "iptal" && kalan > 0 && <Satir ad="Kalan">{paraBicimle(String(kalan))}</Satir>}
        </dl>

        <div>
          <h4 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-metin-soluk mb-1">Ödemeler</h4>
          {odemeler.length === 0 ? (
            <p className="text-sm text-metin-soluk">Henüz ödeme alınmadı.</p>
          ) : (
            <ul aria-label={`${p.paket_adi} ödemeleri`} className="divide-y divide-cizgi border-y border-cizgi">
              {odemeler.map((o) => (
                <li key={o.id} className={`py-2.5 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-sm ${o.iptal ? "text-metin-soluk" : ""}`}>
                  <div className="min-w-0">
                    <div className={`num ${o.iptal ? "line-through" : "font-medium"}`}>
                      {paraBicimle(o.tutar)} · {YONTEM_ETIKET[o.yontem]}
                    </div>
                    <div className="num text-[12px] text-metin-soluk">
                      {tarihBicimle(o.tarih)}{o.alan_ad ? ` · Alan: ${o.alan_ad}` : ""}
                      {o.iptal && o.iptal_nedeni ? ` · ${o.iptal_nedeni}` : ""}
                    </div>
                  </div>
                  {o.iptal ? (
                    <span className={rozetHata}>Geri alındı</span>
                  ) : (
                    !gizli && p.durum === "odendi" && (
                      <button className={dugme} disabled={mesgul} onClick={() => onGeriAl(o.id)} aria-label={`${paraBicimle(o.tutar)} ödemeyi geri al`}>Geri al</button>
                    )
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex flex-wrap justify-between gap-2">
          <div className="flex flex-wrap gap-2">
            {!gizli && p.durum === "odeme_bekliyor" && (
              <button className={birincilDugme} disabled={mesgul} onClick={onOdemeAl} aria-label={`${p.paket_adi} için ödeme al`}>Ödeme al</button>
            )}
            {iptalEdilebilir && (
              <button className={`${dugme} text-metin-soluk hover:border-hata hover:text-hata`} disabled={mesgul} onClick={onIptal} aria-label={`${p.paket_adi} paketini iptal et`}>Paketi iptal et</button>
            )}
          </div>
          <button className={dugme} onClick={onKapat}>Kapat</button>
        </div>
      </div>
    </Modal>
  );
}

export default function OgrenciPaketleri({ ogrenciId, aktif, onOdemeDegisti }: { ogrenciId: string; aktif: boolean; onOdemeDegisti?: () => void }) {
  const onayla = useOnay();
  const gizli = useTutarGizli();
  const [liste, setListe] = useState<OgrenciPaketi[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [surum, setSurum] = useState(0);
  const [mesgul, setMesgul] = useState(false);
  const [atama, setAtama] = useState<Paket[] | null>(null);
  const [odemeAlinan, setOdemeAlinan] = useState<OgrenciPaketi | null>(null);
  const [geriAlinan, setGeriAlinan] = useState<string | null>(null);
  const [detaydaki, setDetaydaki] = useState<string | null>(null);
  const [tumu, setTumu] = useState(false);

  useEffect(() => {
    let iptal = false;
    ogrenciPaketleriniGetir(ogrenciId)
      .then((v) => { if (!iptal) { setListe(v); setHata(null); } })
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => {
      iptal = true;
    };
  }, [ogrenciId, surum]);

  const detay = liste?.find((x) => x.id === detaydaki) ?? null;
  const gorunen = liste ? (tumu ? liste : liste.slice(0, ILK_GORUNEN)) : [];

  async function atamaAc() {
    setMesgul(true);
    setHata(null);
    try {
      const aktifler = (await paketleriGetir()).filter((p) => p.aktif);
      if (aktifler.length === 0) setHata("Atanabilecek aktif paket yok. Önce Finans > Paketler bölümünden paket tanımlayın.");
      else setAtama(aktifler);
    } catch (e) {
      setHata(hataMesaji(e));
    } finally {
      setMesgul(false);
    }
  }

  async function iptalEt(p: OgrenciPaketi) {
    if (!(await onayla({ baslik: "Paketi iptal et", mesaj: `"${p.paket_adi}" paketi iptal edilsin mi?`, onayYazisi: "İptal et", tehlikeli: true }))) return;
    setMesgul(true);
    setHata(null);
    try {
      await ogrenciPaketiniIptalEt(p.id);
      setSurum((s) => s + 1);
    } catch (e) {
      setHata(hataMesaji(e));
    } finally {
      setMesgul(false);
    }
  }

  return (
    <Kart
      baslik="Paketler"
      sag={gizli ? undefined : <button className={dugme} disabled={mesgul || !aktif} onClick={() => void atamaAc()}>Paket ata</button>}
    >
      <FinansNotu />
      {!aktif && <p className="mb-3 text-sm text-metin-soluk">Öğrenci pasif olduğu için yeni paket atanamaz.</p>}
      {hata && <p role="alert" className="mb-3 text-[13px] text-hata">{hata}</p>}
      {!liste ? (
        !hata && <p className="text-sm text-metin-soluk">Yükleniyor…</p>
      ) : liste.length === 0 ? (
        <p className="text-sm text-metin-soluk">Öğrenciye henüz paket atanmamış.</p>
      ) : (
        <>
          <ul className="-mx-6 border-t border-cizgi">
            {gorunen.map((p) => (
              <li key={p.id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-6 py-3 min-h-[60px] border-t border-cizgi first:border-t-0 text-sm">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{p.paket_adi}</span>
                    <span className={DURUM_ROZET[p.durum]}>{DURUM_ETIKET[p.durum]}</span>
                    {p.fiyat_ozel_mi && <span className={rozetBirincil}>Özel fiyat</span>}
                  </div>
                  <div className="num text-[13px] text-metin-soluk">
                    {p.baslangic && p.bitis ? `${tarihBicimle(p.baslangic)} – ${tarihBicimle(p.bitis)}` : "Tarih belirsiz"} · {p.ders_sayisi} ders
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="num font-medium">{paraBicimle(p.uygulanan_fiyat)}</span>
                  {!gizli && p.durum === "odeme_bekliyor" && (
                    <button className={birincilDugme} disabled={mesgul} onClick={() => setOdemeAlinan(p)} aria-label={`${p.paket_adi} için ödeme al`}>Ödeme al</button>
                  )}
                  <button className={dugme} onClick={() => setDetaydaki(p.id)} aria-label={`${p.paket_adi} detayı`}>Detay</button>
                </div>
              </li>
            ))}
          </ul>
          {liste.length > ILK_GORUNEN && (
            <button type="button" className="mt-3 text-[13px] font-semibold hover:text-altin-metin min-h-11 md:min-h-0" aria-expanded={tumu} onClick={() => setTumu((t) => !t)}>
              {tumu ? "▾ Önceki paketleri gizle" : `▸ Önceki paketleri göster (${liste.length - ILK_GORUNEN})`}
            </button>
          )}
        </>
      )}
      {detay && (
        <PaketDetayPenceresi
          p={detay}
          mesgul={mesgul}
          onKapat={() => setDetaydaki(null)}
          onOdemeAl={() => { setDetaydaki(null); setOdemeAlinan(detay); }}
          onIptal={() => { setDetaydaki(null); void iptalEt(detay); }}
          onGeriAl={(odemeId) => { setDetaydaki(null); setGeriAlinan(odemeId); }}
        />
      )}
      {odemeAlinan && (
        <OdemeAlPenceresi
          hedef={{ ogrenciPaketiId: odemeAlinan.id, paketAdi: odemeAlinan.paket_adi, tutar: odemeAlinan.uygulanan_fiyat ?? "", dersSayisi: odemeAlinan.ders_sayisi }}
          onKapat={() => setOdemeAlinan(null)}
          onTamam={() => { setOdemeAlinan(null); setSurum((s) => s + 1); onOdemeDegisti?.(); }}
        />
      )}
      {geriAlinan && (
        <GeriAlPenceresi
          odemeId={geriAlinan}
          onKapat={() => setGeriAlinan(null)}
          onTamam={() => { setGeriAlinan(null); setSurum((s) => s + 1); onOdemeDegisti?.(); }}
        />
      )}
      {atama && (
        <AtamaPenceresi
          ogrenciId={ogrenciId}
          paketler={atama}
          onKapat={() => setAtama(null)}
          onTamam={() => { setAtama(null); setSurum((s) => s + 1); }}
        />
      )}
    </Kart>
  );
}
