export default function DolulukCubugu({ dolu, kontenjan }: { dolu: number; kontenjan: number }) {
  const oran = kontenjan > 0 ? Math.min(100, Math.round((dolu / kontenjan) * 100)) : 0;
  const renk = oran >= 100 ? "bg-hata" : oran >= 80 ? "bg-altin" : "bg-basari";
  return (
    <div>
      <div className="flex justify-between text-xs text-metin-soluk mb-1">
        <span>Doluluk</span>
        <span>{dolu} / {kontenjan}</span>
      </div>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={kontenjan}
        aria-valuenow={dolu}
        className="h-2 rounded-full bg-yuzey-yuksek overflow-hidden"
      >
        <div className={`h-full ${renk}`} style={{ width: `${oran}%` }} />
      </div>
    </div>
  );
}
