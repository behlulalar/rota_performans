import type { Durum } from "../api/ogrenci";

export default function DurumRozeti({ durum }: { durum: Durum }) {
  const aktif = durum === "aktif";
  return (
    <span
      className={`inline-block rounded-full border px-2.5 py-0.5 text-xs ${
        aktif ? "border-basari/50 text-basari" : "border-cizgi text-metin-soluk"
      }`}
    >
      {aktif ? "Aktif" : "Pasif"}
    </span>
  );
}
