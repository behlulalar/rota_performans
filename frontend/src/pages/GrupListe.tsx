import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { gruplariGetir, type GrupOzet } from "../api/grup";
import DolulukCubugu from "../components/DolulukCubugu";
import { hataMesaji } from "../lib/dogrulama";
import { programOzeti } from "../lib/program";
import SayfaBasligi from "../components/SayfaBasligi";
import { birincilDugme, rozetBasari, rozetNotr, satir, secimKutusu, td, th } from "../lib/stil";

export default function GrupListe() {
  const [filtre, setFiltre] = useState("aktif");
  const [liste, setListe] = useState<GrupOzet[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    let iptal = false;
    setHata(null);
    gruplariGetir(filtre === "" ? undefined : filtre === "aktif")
      .then((v) => !iptal && setListe(v))
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => {
      iptal = true;
    };
  }, [filtre]);

  return (
    <div>
      <SayfaBasligi
        baslik="Gruplar"
        aciklama={liste ? `${liste.length} grup listeleniyor · haftalık program ve doluluk` : "Gruplar, haftalık program ve doluluk"}
        eylemler={<Link to="/gruplar/yeni" className={birincilDugme}>Yeni grup</Link>}
      />
      <div className="mb-4">
        <select
          value={filtre}
          onChange={(e) => setFiltre(e.target.value)}
          aria-label="Durum filtresi"
          className={secimKutusu}
        >
          <option value="">Tüm gruplar</option>
          <option value="aktif">Aktif</option>
          <option value="pasif">Pasif</option>
        </select>
      </div>
      {hata && <p role="alert" className="text-[13px] text-hata mb-3">{hata}</p>}
      {!liste ? (
        <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>
      ) : liste.length === 0 ? (
        <div className="bg-yuzey border border-cizgi rounded-[14px] p-10 text-center text-metin-soluk">Grup bulunamadı.</div>
      ) : (
        <>
          <div className="hidden md:block bg-yuzey border border-cizgi rounded-[14px] overflow-hidden">
            <table className="w-full text-[13px]">
              <thead>
                <tr>
                  <th className={th}>Grup</th>
                  <th className={th}>Antrenör</th>
                  <th className={th}>Program</th>
                  <th className={`${th} w-48`}>Doluluk</th>
                  <th className={th}>Durum</th>
                </tr>
              </thead>
              <tbody>
                {liste.map((g) => (
                  <tr key={g.id} className={satir}>
                    <td className={`${td} font-medium`}>
                      <Link to={`/gruplar/${g.id}`} className="hover:text-altin-metin">{g.ad}</Link>
                    </td>
                    <td className={`${td} text-metin-orta`}>{g.antrenor?.ad_soyad ?? "Antrenör atanmamış"}</td>
                    <td className={`${td} num`}>{programOzeti(g.program)}</td>
                    <td className="px-4 py-1.5 h-[52px]"><DolulukCubugu dolu={g.ogrenci_sayisi} kontenjan={g.kontenjan} /></td>
                    <td className={td}><span className={g.aktif ? rozetBasari : rozetNotr}>{g.aktif ? "Aktif" : "Pasif"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="md:hidden space-y-2">
            {liste.map((g) => (
              <li key={g.id}>
                <Link to={`/gruplar/${g.id}`} className="block bg-yuzey border border-cizgi rounded-[14px] p-4 hover:border-altin transition-colors space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-medium">{g.ad}</span>
                    <span className={g.aktif ? rozetBasari : rozetNotr}>{g.aktif ? "Aktif" : "Pasif"}</span>
                  </div>
                  <div className="text-[13px] text-metin-soluk">{g.antrenor?.ad_soyad ?? "Antrenör atanmamış"}</div>
                  <div className="num text-[13px]">{programOzeti(g.program)}</div>
                  <DolulukCubugu dolu={g.ogrenci_sayisi} kontenjan={g.kontenjan} />
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
