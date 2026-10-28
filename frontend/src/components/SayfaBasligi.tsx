import { createContext, useContext, type ReactNode } from "react";

/** Kabuk, geçerli bölüm adını sayfa başlıklarına bu bağlamla iletir. */
export const BolumBaglami = createContext("");
export const useBolum = () => useContext(BolumBaglami);

/** Büyük başlık, altında açıklama; sağda eylemler. `bolum` verilirse üstte küçük etiket çıkar. */
export default function SayfaBasligi({
  baslik,
  bolum,
  aciklama,
  rozet,
  eylemler,
}: {
  baslik: string;
  bolum?: string;
  aciklama?: ReactNode;
  rozet?: ReactNode;
  eylemler?: ReactNode;
}) {
  return (
    <header className="mb-7 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="min-w-0">
        {bolum && <div className="eyebrow mb-1.5">{bolum}</div>}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h1 className="font-display text-[28px] md:text-[34px] leading-[1.1] break-words">{baslik}</h1>
          {rozet}
        </div>
        {aciklama && <p className="num mt-2 text-[15px] text-metin-soluk">{aciklama}</p>}
      </div>
      {eylemler && <div className="flex flex-wrap items-center gap-2">{eylemler}</div>}
    </header>
  );
}
