import type { ReactNode } from "react";
import { kartKutusu } from "../lib/stil";

/**
 * Editoryal kart: serif başlık, altında soluk açıklama, sağda isteğe bağlı eylem.
 * `bosluksuz` ise gövde kenar boşluksuzdur (liste/tablo için); başlık yine 24px dolgulu kalır.
 */
export default function Kart({
  baslik,
  aciklama,
  sag,
  children,
  bosluksuz = false,
  sinif = "",
  vurgulu = false,
}: {
  baslik?: ReactNode;
  aciklama?: ReactNode;
  sag?: ReactNode;
  children: ReactNode;
  bosluksuz?: boolean;
  sinif?: string;
  vurgulu?: boolean;
}) {
  return (
    <section className={`${vurgulu ? "bg-yuzey border border-altin/60 rounded-[14px]" : kartKutusu} overflow-hidden ${sinif}`}>
      {baslik && (
        <div className="px-6 pt-6 pb-4 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="font-display text-[19px] leading-[1.25]">{baslik}</h2>
            {aciklama && <p className="mt-1 text-sm text-metin-soluk">{aciklama}</p>}
          </div>
          {sag && <div className="flex items-center gap-2 shrink-0">{sag}</div>}
        </div>
      )}
      <div className={bosluksuz ? "" : baslik ? "px-6 pb-6" : "p-6"}>{children}</div>
    </section>
  );
}
