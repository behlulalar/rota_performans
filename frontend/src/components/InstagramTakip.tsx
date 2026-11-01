export const instagramAdresi = (kullanici: string) => `https://www.instagram.com/${kullanici}/`;

export function InstagramSimgesi({ boyut = 18 }: { boyut?: number }) {
  return (
    <svg width={boyut} height={boyut} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="2.5" y="2.5" width="13" height="13" rx="3.8" />
      <circle cx="9" cy="9" r="3" />
      <circle cx="12.9" cy="5.1" r=".5" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** Instagram'ın renk geçişli rozeti içinde beyaz simge. */
function Rozet({ boyut }: { boyut: string }) {
  return (
    <span className={`grid place-items-center shrink-0 rounded-[12px] text-white bg-[linear-gradient(45deg,#f9ce34,#ee2a7b_55%,#6228d7)] ${boyut}`}>
      <InstagramSimgesi boyut={20} />
    </span>
  );
}

/**
 * "Bizi Instagram'da takip edin" kartı. `sade`: giriş sayfası için kenarlıksız, küçük satır.
 * Kullanıcı adı yoksa hiçbir şey göstermez.
 */
export default function InstagramTakip({ kullanici, sade = false }: { kullanici: string | null | undefined; sade?: boolean }) {
  if (!kullanici) return null;
  const ortak = { href: instagramAdresi(kullanici), target: "_blank", rel: "noopener noreferrer" };
  if (sade) {
    return (
      <a {...ortak} className="group inline-flex items-center gap-3 rounded-full border border-cizgi bg-yuzey pl-1.5 pr-4 py-1.5 hover:border-altin transition-colors">
        <Rozet boyut="size-9 rounded-full" />
        <span className="text-[13px] leading-tight">
          <span className="block text-metin-soluk">Bizi Instagram'da takip edin</span>
          <span className="block font-medium group-hover:text-altin-metin">@{kullanici}</span>
        </span>
      </a>
    );
  }
  return (
    <a {...ortak} className="group flex items-center gap-4 bg-yuzey border border-cizgi rounded-[14px] p-5 hover:border-altin transition-colors">
      <Rozet boyut="size-12" />
      <span className="min-w-0 flex-1">
        <span className="block font-display text-[17px] leading-snug">Bizi Instagram'da takip edin</span>
        <span className="block text-[13px] text-metin-soluk">Antrenmanlardan kareler, duyurular ve başarılar · @{kullanici}</span>
      </span>
      <span className="shrink-0 rounded-[10px] bg-birincil text-birincil-metin px-3.5 min-h-9 grid place-items-center text-[13px] font-medium group-hover:opacity-90">Takip et</span>
    </a>
  );
}
