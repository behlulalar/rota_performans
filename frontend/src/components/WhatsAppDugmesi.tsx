import { whatsappAdresi } from "../lib/telefon";

export function WhatsAppSimgesi({ boyut = 18 }: { boyut?: number }) {
  return (
    <svg width={boyut} height={boyut} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9 2a7 7 0 0 0-6 10.6L2 16l3.5-.9A7 7 0 1 0 9 2z" />
      <path d="M6.6 6.2c.3-.5.8-.4 1 0l.5 1c.1.3 0 .5-.3.8-.3.3-.2.5.2 1 .5.6 1 .9 1.6 1.1.3.1.5 0 .7-.3.2-.3.5-.3.8-.1l.9.5c.4.2.4.6.1 1-.5.6-1.2.8-2 .5-1.8-.6-3-1.9-3.6-3.3-.2-.5-.1-1.2.1-1.7z" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** Numaranın WhatsApp sohbetini yeni sekmede açar. Numara geçerli değilse hiçbir şey göstermez. */
export default function WhatsAppDugmesi({ telefon, ad }: { telefon: string | null | undefined; ad: string }) {
  const adres = whatsappAdresi(telefon);
  if (!adres) return null;
  return (
    <a
      href={adres}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`${ad} ile WhatsApp'ta yaz`}
      className="inline-flex items-center gap-1.5 rounded-[10px] bg-[#25D366] px-3 min-h-9 text-[13px] font-medium text-black hover:brightness-95"
    >
      <WhatsAppSimgesi boyut={16} />
      WhatsApp
    </a>
  );
}
