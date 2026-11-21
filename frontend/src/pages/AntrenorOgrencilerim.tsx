import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ogrencilerimGetir, type GrupDevami } from "../api/devam";
import { DevamKisa, UYARI_ESIGI } from "../components/DevamOzeti";
import Kart from "../components/Kart";
import SayfaBasligi from "../components/SayfaBasligi";
import { hataMesaji } from "../lib/dogrulama";
import { hataKutusu, listeSatiri, dugme, rozetUyari, uyariKutusu } from "../lib/stil";

/** Antrenörün kendi gruplarındaki öğrenciler ve devam özetleri. */
export default function AntrenorOgrencilerim() {
  const [gruplar, setGruplar] = useState<GrupDevami[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  const yukle = useCallback(() => ogrencilerimGetir().then(setGruplar, (e) => setHata(hataMesaji(e))), []);
  useEffect(() => { void yukle(); }, [yukle]);

  const dikkat = gruplar?.flatMap((g) => g.ogrenciler).filter((s) => s.devam.ard_arda_gelmedi >= UYARI_ESIGI) ?? [];

  return (
    <>
      <SayfaBasligi baslik="Öğrencilerim" aciklama="Gruplarınızdaki öğrencilerin devam durumu. Oran son 30 güne göredir." />
      {hata && <p role="alert" className={hataKutusu}>{hata}</p>}
      {dikkat.length > 0 && (
        <p role="status" className={`${uyariKutusu} mb-4`}>
          {dikkat.length} öğrenci art arda {UYARI_ESIGI} veya daha fazla derse gelmedi: {dikkat.map((s) => `${s.ad} ${s.soyad}`).join(", ")}.
        </p>
      )}
      {gruplar?.length === 0 && <Kart><p className="text-sm text-metin-soluk">Size atanmış aktif grup yok.</p></Kart>}
      <div className="space-y-4">
        {gruplar?.map((g) => (
          <Kart key={g.grup_id} baslik={g.grup_ad} aciklama={`${g.ogrenciler.length} öğrenci`} bosluksuz>
            {g.ogrenciler.length === 0 ? (
              <p className="px-6 pb-6 text-sm text-metin-soluk">Grupta öğrenci yok.</p>
            ) : (
              <ul className="px-6 pb-3">
                {g.ogrenciler.map((s) => (
                  <li key={s.ogrenci_id} className={listeSatiri}>
                    <div className="py-2.5 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 min-w-0">
                        <span className="flex items-center gap-2 text-sm font-medium">
                          {s.ad} {s.soyad}
                          {(s.telafi_planlanabilir ?? s.telafi_bakiyesi ?? 0) > 0 && <span className={rozetUyari}>Telafi {s.telafi_planlanabilir ?? s.telafi_bakiyesi}</span>}
                        </span>
                        <DevamKisa d={s.devam} />
                      </div>
                      <Link
                        to={`/ogrencilerim/${s.ogrenci_id}/planla`}
                        className={`${dugme} min-h-11 w-full sm:w-auto justify-center`}
                        aria-label={`Ders planla: ${s.ad} ${s.soyad}`}
                      >
                        Ders planla
                      </Link>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Kart>
        ))}
      </div>
      <p className="mt-4 text-xs text-metin-soluk">Noktalar son 10 dersi eskiden yeniye gösterir: yeşil geldi, kırmızı gelmedi, sarı halka telafi, mavi halka ek ders.</p>
    </>
  );
}
