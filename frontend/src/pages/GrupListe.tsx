import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { gruplariGetir, type GrupOzet } from "../api/grup";
import DolulukCubugu from "../components/DolulukCubugu";
import { hataMesaji } from "../lib/dogrulama";
import { programOzeti } from "../lib/program";

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
      <div className="flex items-center justify-between gap-3 mb-4">
        <h1 className="text-xl font-semibold">Gruplar</h1>
        <Link to="/gruplar/yeni" className="rounded-lg bg-altin text-zemin font-semibold px-4 py-2 text-sm hover:bg-altin-acik">Yeni grup</Link>
      </div>
      <div className="mb-4">
        <select
          value={filtre}
          onChange={(e) => setFiltre(e.target.value)}
          aria-label="Durum filtresi"
          className="rounded-lg bg-yuzey border border-cizgi px-3 py-2.5 outline-none focus:border-altin"
        >
          <option value="">Tüm gruplar</option>
          <option value="aktif">Aktif</option>
          <option value="pasif">Pasif</option>
        </select>
      </div>
      {hata && <p role="alert" className="text-sm text-hata mb-3">{hata}</p>}
      {!liste ? (
        <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>
      ) : liste.length === 0 ? (
        <div className="bg-yuzey border border-cizgi rounded-2xl p-10 text-center text-metin-soluk">Grup bulunamadı.</div>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {liste.map((g) => (
            <li key={g.id}>
              <Link to={`/gruplar/${g.id}`} className="block h-full bg-yuzey border border-cizgi rounded-2xl p-4 hover:border-altin transition-colors space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <span className="font-semibold">{g.ad}</span>
                  <span className={`inline-block rounded-full border px-2.5 py-0.5 text-xs ${g.aktif ? "border-basari/50 text-basari" : "border-cizgi text-metin-soluk"}`}>
                    {g.aktif ? "Aktif" : "Pasif"}
                  </span>
                </div>
                <div className="text-sm text-metin-soluk">{g.antrenor?.ad_soyad ?? "Antrenör atanmamış"}</div>
                <div className="text-sm">{programOzeti(g.program)}</div>
                <DolulukCubugu dolu={g.ogrenci_sayisi} kontenjan={g.kontenjan} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
