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
  ton?: "normal" | "altin" | "uyari" | "vurgu";
}) {
  // `vurgu`: marka rengiyle dolu kutu (açık temada siyah-altın, koyu temada altın-siyah).
  const vurgu = ton === "vurgu";
  const renk = vurgu ? "text-birincil-metin" : ton === "uyari" ? "text-uyari" : ton === "altin" ? "text-altin-metin" : "text-metin";
  return (
    <div className={`${vurgu ? "bg-birincil border border-birincil" : "bg-yuzey border border-cizgi"} rounded-[14px] p-5 min-w-0`}>
      <div className={`text-[11px] font-semibold uppercase tracking-[0.12em] ${vurgu ? "text-birincil-metin opacity-75" : "text-metin-soluk"}`}>{etiket}</div>
      <div className={`num font-display text-[32px] leading-[1.15] mt-2 ${renk}`}>{deger}</div>
      {ipucu && <div className={`num text-xs mt-1 ${vurgu ? "text-birincil-metin opacity-75" : "text-metin-soluk"}`}>{ipucu}</div>}
    </div>
  );
}
