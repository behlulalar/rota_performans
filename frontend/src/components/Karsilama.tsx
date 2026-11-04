import type { ReactNode } from "react";
import ArkaPlan from "./ArkaPlan";
import Logo from "./Logo";
import TemaDugmesi from "./TemaDugmesi";

/** Giriş ve zorunlu şifre sayfalarının ortak iskeleti: siyah marka çubuğu, karşılama metni ve form kartı. */
export default function Karsilama({
  baslik,
  aciklama,
  alt,
  arkaPlan = false,
  children,
}: {
  baslik: ReactNode;
  aciklama?: ReactNode;
  /** Karşılama metninin altında (ör. Instagram bağlantısı). */
  alt?: ReactNode;
  /** Arkada bulanık havuz görseli gösterir. */
  arkaPlan?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="relative isolate min-h-[calc(100dvh/var(--olcek,1))] flex flex-col">
      {arkaPlan && <ArkaPlan />}
      <div aria-hidden="true" className="giris-dalga fixed inset-x-0 bottom-0 h-24 -z-10 pointer-events-none" />
      <header className="h-14 shrink-0 flex items-center gap-3 px-4 md:px-6 bg-serit text-white">
        <Logo />
        <span className="flex-1 font-display text-[17px] leading-none">Rota Performans Akademi</span>
        <TemaDugmesi gorunum="serit" />
      </header>
      <main className="flex-1 w-full max-w-5xl mx-auto px-4 md:px-8 py-8 md:py-16 grid gap-6 md:gap-16 md:grid-cols-[1fr_380px] content-start md:content-center md:items-center">
        <div>
          <div aria-label="Rota Performans Akademi" className="giris-imza mb-3 text-[26px] md:text-[32px] leading-none text-altin-metin">
            <span aria-hidden="true">Rota Performans Akademi</span>
          </div>
          <h1 className="giris-belir font-display text-[34px] md:text-[48px] leading-[1.05] text-balance">{baslik}</h1>
          {aciklama && <p className="giris-belir giris-belir-2 mt-3 text-[15px] md:text-[16px] text-metin-soluk max-w-sm">{aciklama}</p>}
          {alt && <div className="giris-belir giris-belir-3 mt-6">{alt}</div>}
        </div>
        <div className="giris-belir giris-belir-2">{children}</div>
      </main>
    </div>
  );
}
