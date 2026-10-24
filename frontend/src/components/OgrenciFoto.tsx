import { useEffect, useRef, useState } from "react";
import { apiBlob } from "../lib/api";

type Props = {
  id: string;
  fotoVar: boolean;
  ad: string;
  soyad: string;
  boyut: "kucuk" | "buyuk";
  sinif?: string; // boyut ve şekil sınıfları
  surum?: number; // değiştiğinde fotoğraf yeniden yüklenir
};

export default function OgrenciFoto({ id, fotoVar, ad, soyad, boyut, sinif = "size-10 rounded-full", surum = 0 }: Props) {
  const kap = useRef<HTMLDivElement>(null);
  const [gorunur, setGorunur] = useState(false);
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    const el = kap.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setGorunur(true);
      return;
    }
    const gozlemci = new IntersectionObserver((k) => {
      if (k.some((x) => x.isIntersecting)) {
        setGorunur(true);
        gozlemci.disconnect();
      }
    });
    gozlemci.observe(el);
    return () => gozlemci.disconnect();
  }, []);

  useEffect(() => {
    if (!gorunur || !fotoVar) {
      setUrl(null);
      return;
    }
    let iptal = false;
    let olusan: string | null = null;
    apiBlob(`/api/ogrenciler/${id}/foto?boyut=${boyut}&v=${surum}`)
      .then((b) => {
        if (iptal) return;
        olusan = URL.createObjectURL(b);
        setUrl(olusan);
      })
      .catch(() => {
        if (!iptal) setUrl(null);
      });
    return () => {
      iptal = true;
      if (olusan) URL.revokeObjectURL(olusan);
    };
  }, [gorunur, fotoVar, id, boyut, surum]);

  const bas = `${ad.charAt(0)}${soyad.charAt(0)}`.toLocaleUpperCase("tr-TR");
  return (
    <div
      ref={kap}
      className={`${sinif} shrink-0 overflow-hidden bg-yuzey-yuksek border border-cizgi grid place-items-center text-altin text-sm font-semibold`}
    >
      {url ? <img src={url} alt={`${ad} ${soyad}`} className="size-full object-cover" /> : bas}
    </div>
  );
}
