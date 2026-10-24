import type { ReactNode } from "react";
import { useKabuk } from "./Kabuk";
import { Ok } from "./Simge";

/** Üst etiket (bölüm adı) → büyük serif başlık → açıklama; sağda eylemler. */
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
  const kabuk = useKabuk();
  return (
    <header className="mb-7 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="min-w-0">
        <div className="eyebrow flex items-center gap-1.5">
          {kabuk.menuGizli && (
            <button
              type="button"
              onClick={kabuk.menuyuGoster}
              aria-label="Menüyü göster"
              title="Menüyü göster"
              className="hidden md:grid place-items-center size-7 -ml-1.5 rounded-[3px] border border-cizgi bg-yuzey text-metin-soluk hover:text-metin hover:border-cizgi-guclu"
            >
              <Ok yon="sag" />
            </button>
          )}
          <span>{bolum ?? kabuk.bolumAdi}</span>
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
          <h1 className="font-display font-medium text-[28px] md:text-[38px] leading-[1.1] break-words">{baslik}</h1>
          {rozet}
        </div>
        {aciklama && <p className="num mt-2 text-[15px] text-metin-soluk">{aciklama}</p>}
      </div>
      {eylemler && <div className="flex flex-wrap items-center gap-2">{eylemler}</div>}
    </header>
  );
}
