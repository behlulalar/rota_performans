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
import Kart from "./Kart";
import Modal from "./Modal";
import OdemeAlPenceresi from "./OdemeAlPenceresi";
import { useOnay } from "../components/OnayPenceresi";

const DURUM_ROZET: Record<PaketDurum, string> = {
  odeme_bekliyor: rozetUyari,
  odendi: rozetBasari,
  iptal: rozetNotr,
};
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
          Dersler bu arada kullanıldıysa ders bakiyesi eksiye düşebilir.
        </p>
        <label className="block"><span className="text-sm text-metin-soluk">Geri alma nedeni</span>
          <input className={girdi} value={neden} onChange={(e) => setNeden(e.target.value)} maxLength={200} autoFocus /></label>
        {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
        <button type="submit" disabled={mesgul} className={birincilDugme}>{mesgul ? "Geri alınıyor…" : "Ödemeyi geri al"}</button>
      </form>
    </Modal>
  );
}

export default function OgrenciPaketleri({ ogrenciId, aktif, onOdemeDegisti }: { ogrenciId: string; aktif: boolean; onOdemeDegisti?: () => void }) {
  const onayla = useOnay();
  const [liste, setListe] = useState<OgrenciPaketi[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [surum, setSurum] = useState(0);
  const [mesgul, setMesgul] = useState(false);
  const [atama, setAtama] = useState<Paket[] | null>(null);
  const [odemeAlinan, setOdemeAlinan] = useState<OgrenciPaketi | null>(null);
  const [geriAlinan, setGeriAlinan] = useState<string | null>(null);

  useEffect(() => {
    let iptal = false;
    ogrenciPaketleriniGetir(ogrenciId)
      .then((v) => { if (!iptal) { setListe(v); setHata(null); } })
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => {
      iptal = true;
    };
  }, [ogrenciId, surum]);

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
      sag={<button className={dugme} disabled={mesgul || !aktif} onClick={() => void atamaAc()}>Paket ata</button>}
    >
      {!aktif && <p className="mb-3 text-sm text-metin-soluk">Öğrenci pasif olduğu için yeni paket atanamaz.</p>}
      {hata && <p role="alert" className="mb-3 text-[13px] text-hata">{hata}</p>}
      {!liste ? (
        !hata && <p className="text-sm text-metin-soluk">Yükleniyor…</p>
      ) : liste.length === 0 ? (
        <p className="text-sm text-metin-soluk">Öğrenciye henüz paket atanmamış.</p>
      ) : (
        <ul className="-mx-6 border-t border-cizgi">
          {liste.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-6 py-3 min-h-[52px] border-t border-cizgi first:border-t-0 text-sm">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{p.paket_adi}</span>
                  <span className={DURUM_ROZET[p.durum]}>{DURUM_ETIKET[p.durum]}</span>
                  {p.fiyat_ozel_mi && <span className={rozetBirincil}>Özel fiyat</span>}
                </div>
                <div className="num text-metin-soluk">
                  {p.ders_sayisi} ders · {p.baslangic && p.bitis ? `${tarihBicimle(p.baslangic)} – ${tarihBicimle(p.bitis)}` : "Tarih belirsiz"}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <div className="num text-right">
                  <div className="font-medium">{paraBicimle(p.uygulanan_fiyat)}</div>
                  {p.fiyat_ozel_mi && <div className="text-xs text-metin-soluk line-through">{paraBicimle(p.liste_fiyati)}</div>}
                  <div className="text-xs text-metin-soluk">Ödenen {paraBicimle(p.toplam_odenen)} / {paraBicimle(p.uygulanan_fiyat)}</div>
                </div>
                {p.durum === "odeme_bekliyor" && (
                  <button className={birincilDugme} disabled={mesgul} onClick={() => setOdemeAlinan(p)} aria-label={`${p.paket_adi} için ödeme al`}>Ödeme al</button>
                )}
                {p.durum === "odeme_bekliyor" && Number(p.toplam_odenen) === 0 && (
                  <button className={dugme} disabled={mesgul} onClick={() => void iptalEt(p)} aria-label={`${p.paket_adi} paketini iptal et`}>İptal et</button>
                )}
              </div>
              {(p.odemeler ?? []).length > 0 && (
                <ul className="basis-full border-t border-cizgi pt-2 space-y-1" aria-label={`${p.paket_adi} ödemeleri`}>
                  {(p.odemeler ?? []).map((o) => (
                    <li key={o.id} className={`flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-[13px] ${o.iptal ? "text-metin-soluk" : ""}`}>
                      <div className="min-w-0">
                        <span className={`num ${o.iptal ? "line-through" : ""}`}>
                          {tarihBicimle(o.tarih)} · {YONTEM_ETIKET[o.yontem]} · {paraBicimle(o.tutar)}
                        </span>
                        <span className="text-metin-soluk"> · {o.alan_ad ? `Alan: ${o.alan_ad}` : "Alan: —"}</span>
                        {o.iptal && <span className={`${rozetHata} ml-2`}>Geri alındı</span>}
                        {o.iptal && o.iptal_nedeni && <span className="text-metin-soluk"> · {o.iptal_nedeni}</span>}
                      </div>
                      {!o.iptal && p.durum === "odendi" && (
                        <button className={dugme} disabled={mesgul} onClick={() => setGeriAlinan(o.id)} aria-label={`${paraBicimle(o.tutar)} ödemeyi geri al`}>Ödemeyi geri al</button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
      {odemeAlinan && (
        <OdemeAlPenceresi
          hedef={{ ogrenciPaketiId: odemeAlinan.id, paketAdi: odemeAlinan.paket_adi, tutar: odemeAlinan.uygulanan_fiyat, dersSayisi: odemeAlinan.ders_sayisi }}
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
