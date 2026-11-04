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
      <header className="h-[var(--ust-yuk)] pt-[var(--sa-ust)] shrink-0 flex items-center gap-3 pl-[max(1rem,var(--sa-sol))] pr-[max(1rem,var(--sa-sag))] md:pl-[max(1.5rem,var(--sa-sol))] md:pr-[max(1.5rem,var(--sa-sag))] bg-serit text-white">
        <Logo />
        <span className="flex-1 font-display text-[17px] leading-none">Rota Performans Akademi</span>
        <TemaDugmesi gorunum="serit" />
      </header>
      {/*
        Yerleşim: 1024 px altında (telefon, tablet) tek sütun, her şey yatay ve dikey ortalı; 1024 px ve üstünde
        metin ile kart yan yana, aralarındaki boşluk sabit ve bütün grup sayfanın ortasında.
      */}
      <main className="flex-1 w-full mx-auto pl-[max(1rem,var(--sa-sol))] pr-[max(1rem,var(--sa-sag))] md:px-8 py-8 md:py-16 grid gap-8 lg:gap-16 content-center justify-center grid-cols-[minmax(0,26rem)] md:grid-cols-[minmax(0,34rem)] lg:grid-cols-[auto_380px] items-center">
        <div className="text-center lg:text-left lg:max-w-[30rem]">
          <div aria-label="Rota Performans Akademi" className="giris-imza mb-3 text-[26px] md:text-[32px] leading-none text-altin-metin">
            <span aria-hidden="true">Rota Performans Akademi</span>
          </div>
          <h1 className="giris-belir font-display text-[34px] md:text-[48px] leading-[1.05] text-balance">{baslik}</h1>
          {aciklama && <p className="giris-belir giris-belir-2 mt-3 text-[15px] md:text-[16px] text-metin-soluk max-w-sm mx-auto lg:mx-0">{aciklama}</p>}
          {alt && <div className="giris-belir giris-belir-3 mt-6 flex justify-center lg:justify-start">{alt}</div>}
        </div>
        <div className="giris-belir giris-belir-2 w-full max-w-[380px] mx-auto lg:mx-0">{children}</div>
      </main>
    </div>
  );
}
