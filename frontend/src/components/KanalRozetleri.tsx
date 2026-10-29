import type { DuyuruOzet, KanalIstatistigi } from "../api/duyuru";
import { rozetBasari, rozetHata, rozetNotr, rozetUyari } from "../lib/stil";

function Rozet({ etiket, secili, k }: { etiket: string; secili: boolean; k: KanalIstatistigi }) {
  if (!secili || k.toplam === 0) return <span className={rozetNotr}>{etiket}: —</span>;
  const sinif = k.hata > 0 ? rozetHata : k.gonderildi === k.toplam ? rozetBasari : k.bekliyor > 0 ? rozetUyari : rozetNotr;
  return (
    <span className={sinif}>
      {etiket}: <span className="num">{k.gonderildi}/{k.toplam}</span> gönderildi
      {k.hata > 0 && <> · <span className="num">{k.hata}</span> hata</>}
    </span>
  );
}

/** Duyurunun kanal başına gönderim özeti: "Uygulama: 19/27 gönderildi", "WhatsApp: —". */
export default function KanalRozetleri({ d }: { d: DuyuruOzet }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      <Rozet etiket="Uygulama" secili={d.kanallar.push} k={d.istatistik.push} />
      <Rozet etiket="WhatsApp" secili={d.kanallar.whatsapp} k={d.istatistik.whatsapp} />
    </div>
  );
}
