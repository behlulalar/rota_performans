import { useState, type FormEvent } from "react";
import { odemeAl, YONTEM_ETIKET, type OdemeYontemi } from "../api/odeme";
import { hataMesaji } from "../lib/dogrulama";
import { paraBicimle } from "../lib/para";
import { bugun } from "../lib/tarih";
import { basariKutusu, birincilDugme, girdi } from "../lib/stil";
import Modal from "./Modal";

export type OdemeHedefi = { ogrenciPaketiId: string; paketAdi: string; tutar: string; dersSayisi?: number; ogrenciAdi?: string };

/** Tam ödeme alma penceresi; hem öğrenci kartında hem Ödemeler sayfasında kullanılır. */
export default function OdemeAlPenceresi({ hedef, onKapat, onTamam }: { hedef: OdemeHedefi; onKapat: () => void; onTamam: () => void }) {
  const [yontem, setYontem] = useState<OdemeYontemi>("nakit");
  const [tarih, setTarih] = useState(bugun());
  const [aciklama, setAciklama] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const [sonuc, setSonuc] = useState<number | null | undefined>(undefined);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    if (!tarih) return setHata("Ödeme tarihi seçin.");
    if (tarih > bugun()) return setHata("Ödeme tarihi gelecekte olamaz.");
    setMesgul(true);
    setHata(null);
    try {
      const govde: { yontem: OdemeYontemi; tarih: string; aciklama?: string } = { yontem, tarih };
      if (aciklama.trim()) govde.aciklama = aciklama.trim();
      await odemeAl(hedef.ogrenciPaketiId, govde);
      setSonuc(hedef.dersSayisi ?? null);
    } catch (err) {
      setHata(hataMesaji(err));
      setMesgul(false);
    }
  }

  const baslik = "Ödeme al";
  if (sonuc !== undefined) {
    return (
      <Modal baslik={baslik} onKapat={onTamam}>
        <div className="space-y-3">
          <p role="status" className={basariKutusu}>
            Ödeme alındı.{sonuc ? ` ${sonuc} ders hakkı yüklendi.` : " Ders hakkı yüklendi."}
          </p>
          <button type="button" className={birincilDugme} onClick={onTamam}>Tamam</button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal baslik={baslik} onKapat={onKapat}>
      <form onSubmit={gonder} noValidate className="space-y-3">
        <p className="text-sm text-metin-soluk">
          {hedef.ogrenciAdi ? `${hedef.ogrenciAdi} · ` : ""}{hedef.paketAdi}
        </p>
        <div>
          <span className="text-sm text-metin-soluk">Tutar (Tam ödeme)</span>
          <div className={`${girdi} flex items-center num font-medium opacity-80`} aria-label="Tutar">{paraBicimle(hedef.tutar)}</div>
        </div>
        <label className="block"><span className="text-sm text-metin-soluk">Ödeme yöntemi</span>
          <select className={`${girdi} bg-zemin`} value={yontem} onChange={(e) => setYontem(e.target.value as OdemeYontemi)}>
            {(Object.keys(YONTEM_ETIKET) as OdemeYontemi[]).map((y) => <option key={y} value={y}>{YONTEM_ETIKET[y]}</option>)}
          </select></label>
        <label className="block"><span className="text-sm text-metin-soluk">Ödeme tarihi</span>
          <input className={girdi} type="date" value={tarih} max={bugun()} onChange={(e) => setTarih(e.target.value)} /></label>
        <label className="block"><span className="text-sm text-metin-soluk">Açıklama (isteğe bağlı)</span>
          <input className={girdi} value={aciklama} onChange={(e) => setAciklama(e.target.value)} maxLength={300} /></label>
        {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
        <button type="submit" disabled={mesgul} className={birincilDugme}>{mesgul ? "Kaydediliyor…" : "Ödemeyi onayla"}</button>
      </form>
    </Modal>
  );
}
