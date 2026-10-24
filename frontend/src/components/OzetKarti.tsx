/** Özet kartı: büyük harf etiket, serif değer, ipucu satırı. Ton: vurgu rengi. */
export default function OzetKarti({
  etiket,
  deger,
  ipucu,
  ton = "normal",
}: {
  etiket: string;
  deger: string | number;
  ipucu?: string;
  ton?: "normal" | "altin" | "uyari";
}) {
  const renk = ton === "uyari" ? "text-uyari" : ton === "altin" ? "text-altin-metin" : "text-metin";
  return (
    <div className="bg-yuzey border border-cizgi rounded-[5px] p-5 min-w-0">
      <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-metin-soluk">{etiket}</div>
      <div className={`num font-display font-medium text-[32px] leading-[1.15] mt-2 ${renk}`}>{deger}</div>
      {ipucu && <div className="num text-xs text-metin-soluk mt-1">{ipucu}</div>}
    </div>
  );
}
