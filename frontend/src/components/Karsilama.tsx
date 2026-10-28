import type { ReactNode } from "react";
import Logo from "./Logo";
import TemaDugmesi from "./TemaDugmesi";

/** Giriş ve zorunlu şifre sayfalarının ortak iskeleti: siyah marka çubuğu, karşılama metni ve form kartı. */
export default function Karsilama({
  baslik,
  aciklama,
  children,
}: {
  baslik: ReactNode;
  aciklama?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="min-h-dvh flex flex-col">
      <header className="h-14 shrink-0 flex items-center gap-3 px-4 md:px-6 bg-serit text-white">
        <Logo />
        <span className="flex-1 font-display text-[17px] leading-none">Rota Performans Akademi</span>
        <TemaDugmesi gorunum="serit" />
      </header>
      <main className="flex-1 w-full max-w-5xl mx-auto px-4 md:px-8 py-8 md:py-16 grid gap-6 md:gap-16 md:grid-cols-[1fr_380px] content-start md:content-center md:items-center">
        <div>
          <h1 className="font-display text-[34px] md:text-[48px] leading-[1.05] text-balance">{baslik}</h1>
          {aciklama && <p className="mt-3 text-[15px] md:text-[16px] text-metin-soluk max-w-sm">{aciklama}</p>}
        </div>
        <div>{children}</div>
      </main>
    </div>
  );
}
