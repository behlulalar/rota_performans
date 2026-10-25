import { useEffect, useState, type FormEvent } from "react";
import {
  DURUM_ETIKET, ogrenciPaketiniIptalEt, ogrenciPaketleriniGetir, paketAta, paketleriGetir,
  type OgrenciPaketi, type Paket, type PaketDurum,
} from "../api/paket";
import { hataMesaji, tarihBicimle } from "../lib/dogrulama";
import { paraBicimle } from "../lib/para";
import { bugun } from "../lib/tarih";
import { birincilDugme, dugme, girdi, rozetBasari, rozetBirincil, rozetNotr, rozetUyari } from "../lib/stil";
import Kart from "./Kart";
import Modal from "./Modal";

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

export default function OgrenciPaketleri({ ogrenciId, aktif }: { ogrenciId: string; aktif: boolean }) {
  const [liste, setListe] = useState<OgrenciPaketi[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [surum, setSurum] = useState(0);
  const [mesgul, setMesgul] = useState(false);
  const [atama, setAtama] = useState<Paket[] | null>(null);

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
    if (!window.confirm(`"${p.paket_adi}" paketi iptal edilsin mi?`)) return;
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
                {p.durum === "odeme_bekliyor" && Number(p.toplam_odenen) === 0 && (
                  <button className={dugme} disabled={mesgul} onClick={() => void iptalEt(p)} aria-label={`${p.paket_adi} paketini iptal et`}>İptal et</button>
                )}
              </div>
            </li>
          ))}
        </ul>
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
