export default function DolulukCubugu({
  dolu,
  kontenjan,
  yalnizCubuk = false,
}: {
  dolu: number;
  kontenjan: number;
  /** Etiket satırı olmadan yalnızca çubuk (sayılar başka yerde yazılıyorsa). */
  yalnizCubuk?: boolean;
}) {
  const oran = kontenjan > 0 ? Math.min(100, Math.round((dolu / kontenjan) * 100)) : 0;
  const renk = oran >= 100 ? "bg-hata" : oran >= 80 ? "bg-altin" : "bg-basari";
  return (
    <div>
      {!yalnizCubuk && (
        <div className="flex justify-between text-[11px] text-metin-soluk mb-1">
          <span>Doluluk</span>
          <span className="num">{dolu} / {kontenjan}</span>
        </div>
      )}
      <div
        role="progressbar"
        aria-label="Doluluk"
        aria-valuemin={0}
        aria-valuemax={kontenjan}
        aria-valuenow={dolu}
        className="h-1.5 rounded-full bg-yuzey-yuksek overflow-hidden"
      >
        <div className={`h-full ${renk}`} style={{ width: `${oran}%` }} />
      </div>
    </div>
  );
}
