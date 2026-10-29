import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { duyurulariGetir, type DuyuruOzet } from "../api/duyuru";
import KanalRozetleri from "../components/KanalRozetleri";
import SayfaBasligi from "../components/SayfaBasligi";
import { hataMesaji } from "../lib/dogrulama";
import { birincilDugme, kartKutusu } from "../lib/stil";

export const zaman = (iso: string) =>
  new Date(iso).toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });

export default function Duyurular() {
  const [liste, setListe] = useState<DuyuruOzet[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    let iptal = false;
    duyurulariGetir()
      .then((v) => !iptal && setListe(v))
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => { iptal = true; };
  }, []);

  return (
    <div>
      <SayfaBasligi
        baslik="Duyurular"
        aciklama="Velilere elle gönderilen duyurular"
        eylemler={<Link to="/duyurular/yeni" className={birincilDugme}>Yeni duyuru</Link>}
      />
      {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
      {!liste ? (
        !hata && <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>
      ) : liste.length === 0 ? (
        <div className={`${kartKutusu} p-10 text-center text-metin-soluk`}>Henüz duyuru gönderilmedi.</div>
      ) : (
        <ul className="space-y-3" aria-label="Duyurular">
          {liste.map((d) => (
            <li key={d.id} className={`${kartKutusu} p-4`}>
              <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
                <Link to={`/duyurular/${d.id}`} className="font-medium hover:text-altin-metin min-w-0 break-words">{d.baslik}</Link>
                <span className="num text-xs text-metin-soluk">{zaman(d.olusturma)}</span>
              </div>
              <div className="mt-0.5 text-[13px] text-metin-soluk">{d.hedef_ozet}</div>
              <p className="mt-2 text-[13px] text-metin-orta line-clamp-2 break-words">{d.metin}</p>
              <div className="mt-3"><KanalRozetleri d={d} /></div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
