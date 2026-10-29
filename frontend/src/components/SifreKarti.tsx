import { useState, type FormEvent } from "react";
import { sifreDegistir } from "../api/veli";
import { hataMesaji, yeniSifreHatasi } from "../lib/dogrulama";
import { basariKutusu, birincilDugme, girdi } from "../lib/stil";
import Kart from "./Kart";

/** Oturum açmış herkesin kendi şifresini değiştirdiği kart (veli ve antrenör profili ortak kullanır). */
export default function SifreKarti() {
  const [mevcut, setMevcut] = useState("");
  const [yeni, setYeni] = useState("");
  const [tekrar, setTekrar] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [tamam, setTamam] = useState(false);
  const [mesgul, setMesgul] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    setTamam(false);
    const h = !mevcut ? "Mevcut şifrenizi girin." : yeniSifreHatasi(mevcut, yeni) ?? (tekrar !== yeni ? "Şifreler eşleşmiyor." : null);
    if (h) return setHata(h);
    setMesgul(true);
    setHata(null);
    try {
      await sifreDegistir(mevcut, yeni);
      setMevcut("");
      setYeni("");
      setTekrar("");
      setTamam(true);
    } catch (err) {
      setHata(hataMesaji(err));
    } finally {
      setMesgul(false);
    }
  }

  return (
    <Kart baslik="Şifre değiştir" aciklama="Başka cihazlardaki oturumlar kapatılır">
      <form onSubmit={gonder} noValidate className="space-y-4 max-w-md">
        <label className="block">
          <span className="text-[13px] text-metin-soluk">Mevcut şifre</span>
          <input className={girdi} type="password" value={mevcut} onChange={(e) => setMevcut(e.target.value)} autoComplete="current-password" />
        </label>
        <label className="block">
          <span className="text-[13px] text-metin-soluk">Yeni şifre</span>
          <input className={girdi} type="password" value={yeni} onChange={(e) => setYeni(e.target.value)} autoComplete="new-password" />
        </label>
        <label className="block">
          <span className="text-[13px] text-metin-soluk">Yeni şifre (tekrar)</span>
          <input className={girdi} type="password" value={tekrar} onChange={(e) => setTekrar(e.target.value)} autoComplete="new-password" />
        </label>
        {hata && (
          <p role="alert" className="text-[13px] text-hata">
            {hata}
          </p>
        )}
        {tamam && (
          <p role="status" className={basariKutusu}>
            Şifreniz değiştirildi.
          </p>
        )}
        <button type="submit" disabled={mesgul} className={birincilDugme}>
          {mesgul ? "Kaydediliyor…" : "Şifreyi değiştir"}
        </button>
      </form>
    </Kart>
  );
}
