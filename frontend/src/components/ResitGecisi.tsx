import { useState, type FormEvent } from "react";
import { resitGecisiYap, type OgrenciDetay } from "../api/ogrenci";
import { hataMesaji } from "../lib/dogrulama";
import TelefonGirdisi from "./TelefonGirdisi";
import { apiyeCevir, gecerliMi, TELEFON_HATA } from "../lib/telefon";
import { girdi, birincilDugme } from "../lib/stil";


export default function ResitGecisi({
  ogrenci,
  onKapat,
  onTamam,
}: {
  ogrenci: { id: string; ad: string; soyad: string };
  onKapat: () => void;
  onTamam: (detay: OgrenciDetay) => void;
}) {
  const [telefon, setTelefon] = useState("");
  const [adSoyad, setAdSoyad] = useState(`${ogrenci.ad} ${ogrenci.soyad}`);
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    if (!telefon) return setHata("Öğrencinin telefonu zorunludur.");
    if (!gecerliMi(telefon)) return setHata(TELEFON_HATA);
    if (!window.confirm("Reşit geçişi yapılsın mı? Velinin bu öğrenciye panel erişimi kapanır.")) return;
    setGonderiliyor(true);
    setHata(null);
    try {
      const detay = await resitGecisiYap(ogrenci.id, { telefon: apiyeCevir(telefon)!, ad_soyad: adSoyad.trim() || undefined });
      onTamam(detay);
    } catch (err) {
      setHata(hataMesaji(err));
      setGonderiliyor(false);
    }
  }

  return (
    <div className="fixed inset-0 z-30 bg-black/70 grid place-items-center p-4" role="dialog" aria-modal="true" aria-label="Reşit geçişi">
      <div className="w-full max-w-md max-h-full overflow-y-auto bg-yuzey border border-cizgi-guclu rounded-[5px]">
        <div className="flex items-center justify-between px-4 min-h-11 border-b border-cizgi">
          <h2 className="font-display font-medium text-[19px] leading-6">Reşit geçişi: {ogrenci.ad} {ogrenci.soyad}</h2>
          <button onClick={onKapat} className="px-2 min-h-11 text-[13px] text-metin-soluk hover:text-metin" aria-label="Kapat">Kapat</button>
        </div>
        <div className="p-4">
        <p className="text-sm text-metin-soluk mb-3">
          Öğrenci 18 yaşını doldurdu. Birincil iletişim kişisi öğrencinin kendisi olur; velinin bu öğrenciye panel erişimi kapanır.
        </p>
        <form onSubmit={gonder} noValidate className="space-y-3">
          <label className="block"><span className="text-sm text-metin-soluk">Öğrencinin telefonu</span>
            <TelefonGirdisi value={telefon} onChange={setTelefon} autoFocus /></label>
          <label className="block"><span className="text-sm text-metin-soluk">Ad soyad</span>
            <input className={girdi} value={adSoyad} onChange={(e) => setAdSoyad(e.target.value)} /></label>
          {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
          <button type="submit" disabled={gonderiliyor} className={birincilDugme}>
            {gonderiliyor ? "Kaydediliyor…" : "Geçişi yap"}
          </button>
        </form>
        </div>
      </div>
    </div>
  );
}
