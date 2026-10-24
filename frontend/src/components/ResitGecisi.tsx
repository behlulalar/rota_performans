import { useState, type FormEvent } from "react";
import { resitGecisiYap, type OgrenciDetay } from "../api/ogrenci";
import { hataMesaji } from "../lib/dogrulama";

const girdi = "mt-1 w-full rounded-lg bg-zemin border border-cizgi px-3 py-2.5 outline-none focus:border-altin";

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
    if (!telefon.trim()) return setHata("Öğrencinin telefonu zorunludur.");
    if (!window.confirm("Reşit geçişi yapılsın mı? Velinin bu öğrenciye panel erişimi kapanır.")) return;
    setGonderiliyor(true);
    setHata(null);
    try {
      const detay = await resitGecisiYap(ogrenci.id, { telefon: telefon.trim(), ad_soyad: adSoyad.trim() || undefined });
      onTamam(detay);
    } catch (err) {
      setHata(hataMesaji(err));
      setGonderiliyor(false);
    }
  }

  return (
    <div className="fixed inset-0 z-30 bg-black/70 grid place-items-center p-4" role="dialog" aria-modal="true" aria-label="Reşit geçişi">
      <div className="w-full max-w-md max-h-full overflow-y-auto bg-yuzey border border-cizgi rounded-2xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">Reşit geçişi: {ogrenci.ad} {ogrenci.soyad}</h2>
          <button onClick={onKapat} className="text-sm text-metin-soluk hover:text-metin" aria-label="Kapat">Kapat</button>
        </div>
        <p className="text-sm text-metin-soluk mb-3">
          Öğrenci 18 yaşını doldurdu. Birincil iletişim kişisi öğrencinin kendisi olur; velinin bu öğrenciye panel erişimi kapanır.
        </p>
        <form onSubmit={gonder} noValidate className="space-y-3">
          <label className="block"><span className="text-sm text-metin-soluk">Öğrencinin telefonu</span>
            <input className={girdi} type="tel" value={telefon} onChange={(e) => setTelefon(e.target.value)} autoFocus /></label>
          <label className="block"><span className="text-sm text-metin-soluk">Ad soyad</span>
            <input className={girdi} value={adSoyad} onChange={(e) => setAdSoyad(e.target.value)} /></label>
          {hata && <p role="alert" className="text-sm text-hata">{hata}</p>}
          <button type="submit" disabled={gonderiliyor} className="rounded-lg bg-altin text-zemin font-semibold px-5 py-2.5 hover:bg-altin-acik disabled:opacity-50">
            {gonderiliyor ? "Kaydediliyor…" : "Geçişi yap"}
          </button>
        </form>
      </div>
    </div>
  );
}
