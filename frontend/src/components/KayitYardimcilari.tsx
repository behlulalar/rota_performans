import { useState } from "react";
import { hataMesaji } from "../lib/dogrulama";
import { basariKutusu, hataKutusu } from "../lib/stil";

export const etiket = "text-[13px] text-metin-soluk";

export function Sonuc({ hata, tamam, mesaj }: { hata: string | null; tamam: boolean; mesaj: string }) {
  return (
    <>
      {hata && <p role="alert" className={hataKutusu}>{hata}</p>}
      {tamam && <p role="status" className={basariKutusu}>{mesaj}</p>}
    </>
  );
}

/** Kaydetme durumu: mesgul/hata/tamam üçlüsü. */
export function useKayit() {
  const [mesgul, setMesgul] = useState(false);
  const [hata, setHata] = useState<string | null>(null);
  const [tamam, setTamam] = useState(false);
  async function calistir(is: () => Promise<void>) {
    setMesgul(true);
    setHata(null);
    setTamam(false);
    try {
      await is();
      setTamam(true);
    } catch (err) {
      setHata(hataMesaji(err));
    } finally {
      setMesgul(false);
    }
  }
  return { mesgul, hata, tamam, setHata, calistir };
}

