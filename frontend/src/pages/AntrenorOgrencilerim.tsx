import { useCallback, useEffect, useState } from "react";
import { antrenorOgrenciTelafiGetir, type AntrenorOgrenciTelafi } from "../api/antrenorPaneli";
import { ogrencilerimGetir, type GrupDevami } from "../api/devam";
import type { TelafiPlani } from "../api/ogrenci";
import { telafiGeriAl } from "../api/takvim";
import { DevamKisa, UYARI_ESIGI } from "../components/DevamOzeti";
import Kart from "../components/Kart";
import { useOnay } from "../components/OnayPenceresi";
import SayfaBasligi from "../components/SayfaBasligi";
import { Pencere, TelafiAdaylari, gunMetni, saat, telafiBasligi } from "../components/TelafiPlanla";
import { hataMesaji } from "../lib/dogrulama";
import { hataKutusu, listeSatiri, birincilDugme, dugme, rozetUyari, uyariKutusu } from "../lib/stil";

const ggAa = (s: string) => `${s.slice(8, 10)}.${s.slice(5, 7)}`;

/** Öğrencinin telafi durumu: planlanabilir hak, planlı telafiler (taşı/kaldır) ve yeni telafi planlama. */
function TelafiAltPencere({ ogrenciId, ad, onKapat, onDegisti }: { ogrenciId: string; ad: string; onKapat: () => void; onDegisti: () => void }) {
  const onayla = useOnay();
  const [d, setD] = useState<AntrenorOgrenciTelafi | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const [asama, setAsama] = useState<{ tur: "planla" } | { tur: "tasi"; plan: TelafiPlani } | null>(null);

  const yukle = useCallback(async () => {
    try {
      setD(await antrenorOgrenciTelafiGetir(ogrenciId));
    } catch (e) {
      setHata(hataMesaji(e));
    }
  }, [ogrenciId]);

  useEffect(() => { void yukle(); }, [yukle]);

  async function kaldir(p: TelafiPlani) {
    if (!(await onayla({ baslik: "Telafiyi kaldır", mesaj: "Telafi planı kaldırılsın mı? Telafi hakkı iade edilir.", onayYazisi: "Kaldır", tehlikeli: true }))) return;
    setMesgul(true);
    setHata(null);
    try {
      await telafiGeriAl(p.oturum_id, ogrenciId);
      await yukle();
      onDegisti();
    } catch (e) {
      setHata(hataMesaji(e));
    } finally {
      setMesgul(false);
    }
  }

  async function bitti() {
    setAsama(null);
    setHata(null);
    await yukle();
    onDegisti();
  }

  const ana = asama === null;
  return (
    <Pencere
      baslik={ana ? ad : telafiBasligi(asama.tur === "tasi" ? asama.plan : undefined)}
      onKapat={onKapat}
      alt
      geri={ana ? undefined : () => { setAsama(null); setHata(null); }}
      altBolum={ana && d ? (
        <>
          <button className={`${birincilDugme} w-full min-h-11`} disabled={mesgul || d.kullanilabilir <= 0} onClick={() => setAsama({ tur: "planla" })}>Telafi planla</button>
          {d.kullanilabilir <= 0 && <p className="mt-2 text-xs text-metin-soluk">Planlanabilir telafi hakkı yok.</p>}
        </>
      ) : undefined}
    >
      {ana && hata && <p role="alert" className="mb-3 text-sm text-hata">{hata}</p>}
      {!ana ? (
        <TelafiAdaylari
          ogrenciId={ogrenciId}
          sonKullanma={d?.son_kullanma ?? null}
          tasinan={asama.tur === "tasi" ? asama.plan : undefined}
          onTamam={() => void bitti()}
        />
      ) : d === null ? (
        !hata && <p className="text-sm text-metin-soluk">Yükleniyor…</p>
      ) : (
        <div className="space-y-4">
          <p className="text-sm">
            Planlanabilir: <span className="num font-semibold">{d.kullanilabilir}</span>
            {d.son_kullanma && <> · son gün <span className="num font-semibold">{ggAa(d.son_kullanma)}</span></>}
          </p>
          <div>
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-metin-soluk mb-2">Planlı telafiler</h3>
            {d.planlar.length === 0 ? (
              <p className="text-sm text-metin-soluk">Planlı telafi yok.</p>
            ) : (
              <ul className="space-y-2">
                {d.planlar.map((p) => (
                  <li key={p.oturum_id} className="rounded-[10px] border border-cizgi px-3 py-2.5 text-sm">
                    <div className="num font-medium">{gunMetni(p.tarih)} · {saat(p.baslangic)}–{saat(p.bitis)}</div>
                    <div className="text-metin-soluk">{p.grup.ad}</div>
                    {p.iptal_edilebilir && p.yoklama === null && (
                      <div className="mt-2 grid grid-cols-2 gap-2">
                        <button className={`${dugme} min-h-11`} disabled={mesgul} onClick={() => setAsama({ tur: "tasi", plan: p })}>Taşı</button>
                        <button className={`${dugme} min-h-11`} disabled={mesgul} onClick={() => void kaldir(p)}>Kaldır</button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </Pencere>
  );
}

/** Antrenörün kendi gruplarındaki öğrenciler ve devam özetleri. */
export default function AntrenorOgrencilerim() {
  const [gruplar, setGruplar] = useState<GrupDevami[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [acik, setAcik] = useState<{ id: string; ad: string } | null>(null);

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
                    <button
                      type="button"
                      onClick={() => setAcik({ id: s.ogrenci_id, ad: `${s.ad} ${s.soyad}` })}
                      className="w-full min-h-[52px] py-2.5 flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5 text-left"
                      aria-label={`${s.ad} ${s.soyad}: telafi`}
                    >
                      <span className="flex items-center gap-2 text-sm font-medium">
                        {s.ad} {s.soyad}
                        {(s.telafi_bakiyesi ?? 0) > 0 && <span className={rozetUyari}>Telafi {s.telafi_bakiyesi}</span>}
                      </span>
                      <DevamKisa d={s.devam} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Kart>
        ))}
      </div>
      {acik && <TelafiAltPencere ogrenciId={acik.id} ad={acik.ad} onKapat={() => setAcik(null)} onDegisti={() => void yukle()} />}
      <p className="mt-4 text-xs text-metin-soluk">Noktalar son 10 dersi eskiden yeniye gösterir: yeşil geldi, kırmızı gelmedi, sarı halka telafi dersi.</p>
    </>
  );
}
