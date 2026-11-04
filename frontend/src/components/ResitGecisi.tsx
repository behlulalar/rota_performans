import { useState, type FormEvent } from "react";
import { resitGecisiYap, type OgrenciDetay } from "../api/ogrenci";
import { hataMesaji } from "../lib/dogrulama";
import TelefonGirdisi from "./TelefonGirdisi";
import { apiyeCevir, bicimle, gecerliMi, numaraCoz, TELEFON_HATA } from "../lib/telefon";
import { girdi, birincilDugme } from "../lib/stil";
import { useOnay } from "../components/OnayPenceresi";


export default function ResitGecisi({
  ogrenci,
  onKapat,
  onTamam,
}: {
  ogrenci: { id: string; ad: string; soyad: string; telefon: string | null };
  onKapat: () => void;
  onTamam: (detay: OgrenciDetay) => void;
}) {
  const onayla = useOnay();
  const [telefon, setTelefon] = useState(numaraCoz(ogrenci.telefon));
  const [adSoyad, setAdSoyad] = useState(`${ogrenci.ad} ${ogrenci.soyad}`);
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    if (!telefon) return setHata("Öğrencinin telefonu zorunludur.");
    if (!gecerliMi(telefon)) return setHata(TELEFON_HATA);
    if (!(await onayla({ baslik: "Reşit geçişi", mesaj: "Reşit geçişi yapılsın mı? Velinin bu öğrenciye panel erişimi kapanır.", onayYazisi: "Geçişi yap" }))) return;
    if (ogrenci.telefon && apiyeCevir(telefon) !== ogrenci.telefon) {
      const onay = await onayla({
        baslik: "Telefon değişecek",
        mesaj: `Girdiğiniz telefon kayıtlı telefondan (${bicimle(ogrenci.telefon)}) farklı. Devam ederseniz öğrencinin kişisel bilgilerindeki ve iletişim telefonu ${bicimle(apiyeCevir(telefon))} olarak değişir. Emin misiniz?`,
        onayYazisi: "Telefonu değiştir",
        tehlikeli: true,
      });
      if (!onay) return;
    }
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
      <div className="w-full max-w-md max-h-full overflow-y-auto bg-yuzey border border-cizgi-guclu rounded-[14px]">
        <div className="flex items-center justify-between px-4 min-h-11 border-b border-cizgi">
          <h2 className="font-display text-[19px] leading-6">Reşit geçişi: {ogrenci.ad} {ogrenci.soyad}</h2>
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
