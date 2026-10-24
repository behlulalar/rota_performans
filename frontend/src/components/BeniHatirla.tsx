type Props = { isaretli: boolean; degisti: (v: boolean) => void };

/** Gerçek onay kutusu (görünmez, tüm alanı kaplar) + özel kutu görünümü; dokunma alanı en az 44px. */
export default function BeniHatirla({ isaretli, degisti }: Props) {
  return (
    <label className="relative flex items-center gap-3 min-h-11 cursor-pointer select-none">
      <input
        type="checkbox"
        checked={isaretli}
        onChange={(e) => degisti(e.target.checked)}
        className="peer absolute inset-0 size-full m-0 opacity-0 cursor-pointer"
      />
      <span
        aria-hidden="true"
        className="size-5 shrink-0 rounded-[3px] border border-cizgi-guclu bg-zemin grid place-items-center text-birincil-metin transition-colors peer-checked:bg-birincil peer-checked:border-birincil peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-altin [&>svg]:opacity-0 peer-checked:[&>svg]:opacity-100"
      >
        <svg viewBox="0 0 16 16" className="size-3.5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3.5 8.5l3 3 6-7" />
        </svg>
      </span>
      <span className="text-[13px] text-metin-orta">Beni hatırla</span>
    </label>
  );
}
