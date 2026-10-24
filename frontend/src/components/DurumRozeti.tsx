import type { Durum } from "../api/ogrenci";
import { rozetBasari, rozetNotr } from "../lib/stil";

export default function DurumRozeti({ durum }: { durum: Durum }) {
  const aktif = durum === "aktif";
  return (
    <span className={aktif ? rozetBasari : rozetNotr}>
      {aktif ? "Aktif" : "Pasif"}
    </span>
  );
}
