import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { birincilDugme, dugme } from "../lib/stil";

export type OnayIstegi = {
  baslik?: string;
  mesaj: ReactNode;
  /** Onay düğmesinin yazısı. */
  onayYazisi?: string;
  /** Geri alınması zor işlemlerde onay düğmesi kırmızı olur. */
  tehlikeli?: boolean;
};

type Onayla = (istek: OnayIstegi | string) => Promise<boolean>;

const OnayBaglami = createContext<Onayla | null>(null);

/** `window.confirm` yerine: `if (!(await onayla("..."))) return;` */
export function useOnay(): Onayla {
  const o = useContext(OnayBaglami);
  if (!o) throw new Error("useOnay, OnayProvider içinde kullanılmalı");
  return o;
}

type Bekleyen = OnayIstegi & { coz: (v: boolean) => void };

export function OnayProvider({ children }: { children: ReactNode }) {
  const [bekleyen, setBekleyen] = useState<Bekleyen | null>(null);
  const onayDugmesi = useRef<HTMLButtonElement>(null);

  const onayla = useCallback<Onayla>(
    (istek) =>
      new Promise<boolean>((coz) => {
        const i = typeof istek === "string" ? { mesaj: istek } : istek;
        setBekleyen((onceki) => {
          onceki?.coz(false);
          return { ...i, coz };
        });
      }),
    [],
  );

  const kapat = useCallback((deger: boolean) => {
    setBekleyen((b) => {
      b?.coz(deger);
      return null;
    });
  }, []);

  useEffect(() => {
    if (!bekleyen) return;
    onayDugmesi.current?.focus();
    const tus = (e: KeyboardEvent) => e.key === "Escape" && kapat(false);
    window.addEventListener("keydown", tus);
    return () => window.removeEventListener("keydown", tus);
  }, [bekleyen, kapat]);

  return (
    <OnayBaglami.Provider value={onayla}>
      {children}
      {bekleyen && (
        <div
          className="fixed inset-0 z-50 bg-black/70 grid place-items-center p-4"
          role="alertdialog"
          aria-modal="true"
          aria-label={bekleyen.baslik ?? "Onay"}
          aria-describedby="onay-mesaj"
          data-onay-penceresi
          onClick={(e) => e.target === e.currentTarget && kapat(false)}
        >
          <div className="w-full max-w-sm bg-yuzey border border-cizgi-guclu rounded-[14px] p-5">
            <h2 className="font-display text-[19px] leading-6">{bekleyen.baslik ?? "Emin misiniz?"}</h2>
            <p id="onay-mesaj" className="mt-2 text-[14px] leading-relaxed text-metin-orta">
              {bekleyen.mesaj}
            </p>
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button type="button" onClick={() => kapat(false)} className={dugme}>
                Vazgeç
              </button>
              <button
                type="button"
                ref={onayDugmesi}
                onClick={() => kapat(true)}
                className={bekleyen.tehlikeli ? `${birincilDugme} !bg-hata !border-hata !text-white` : birincilDugme}
              >
                {bekleyen.onayYazisi ?? "Onayla"}
              </button>
            </div>
          </div>
        </div>
      )}
    </OnayBaglami.Provider>
  );
}
