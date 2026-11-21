import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { antrenorOgrenciTelafiGetir, type AntrenorOgrenciTelafi } from "../api/antrenorPaneli";
import { ogrencilerimGetir } from "../api/devam";
import type { TelafiPlani } from "../api/ogrenci";
import { ekDersCikar, telafiGeriAl } from "../api/takvim";
import Kart from "../components/Kart";
import { useOnay } from "../components/OnayPenceresi";
import SayfaBasligi from "../components/SayfaBasligi";
import { TelafiAdaylari, gunMetni, saat, telafiBasligi } from "../components/TelafiPlanla";
import { hataMesaji, tarihBicimle } from "../lib/dogrulama";
import { basariKutusu, birincilDugme, dugme, hataKutusu, rozetBirincil, rozetUyari } from "../lib/stil";

/** Antrenör: öğrenci için telafi / ek ders planlama sayfası (özet ve aday adımı aynı sayfada, adım adres parametresiyle). */
export default function AntrenorDersPlanla() {
  const { ogrenciId = "" } = useParams();
  const [q] = useSearchParams();
  const gezin = useNavigate();
  const onayla = useOnay();
  const adim = q.get("adim");
  const tur: "telafi" | "ek_ders" | null = adim === "telafi" ? "telafi" : adim === "ek-ders" ? "ek_ders" : null;
  const tasinanId = q.get("tasinan");

  const [d, setD] = useState<AntrenorOgrenciTelafi | null>(null);
  const [ad, setAd] = useState<{ ad: string; gruplar: string[] } | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [bilgi, setBilgi] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);

  const yukle = useCallback(async () => {
    try {
      setD(await antrenorOgrenciTelafiGetir(ogrenciId));
    } catch (e) {
      setHata(hataMesaji(e));
    }
  }, [ogrenciId]);

  useEffect(() => { void yukle(); }, [yukle]);
  useEffect(() => {
    let iptal = false;
    ogrencilerimGetir().then((gruplar) => {
      if (iptal) return;
      const eslesen = gruplar.filter((g) => g.ogrenciler.some((s) => s.ogrenci_id === ogrenciId));
      const s = eslesen[0]?.ogrenciler.find((x) => x.ogrenci_id === ogrenciId);
      if (s) setAd({ ad: `${s.ad} ${s.soyad}`, gruplar: eslesen.map((g) => g.grup_ad) });
    }, () => undefined);
    return () => { iptal = true; };
  }, [ogrenciId]);

  const tasinan: TelafiPlani | undefined = tasinanId ? d?.planlar.find((p) => p.oturum_id === tasinanId) : undefined;
  const ozet = `/ogrencilerim/${ogrenciId}/planla`;
  const adimaGit = (a: "telafi" | "ek-ders", t?: string) => {
    setBilgi(null);
    setHata(null);
    gezin(`${ozet}?adim=${a}${t ? `&tasinan=${t}` : ""}`);
  };

  async function kaldir(p: TelafiPlani) {
    const ek = p.tur === "ek_ders";
    if (!(await onayla(ek
      ? { baslik: "Ek dersi kaldır", mesaj: "Ek ders planı kaldırılsın mı?", onayYazisi: "Kaldır", tehlikeli: true }
      : { baslik: "Telafiyi kaldır", mesaj: "Telafi planı kaldırılsın mı? Telafi hakkı iade edilir.", onayYazisi: "Kaldır", tehlikeli: true }))) return;
    setMesgul(true);
    setHata(null);
    setBilgi(null);
    try {
      await (ek ? ekDersCikar : telafiGeriAl)(p.oturum_id, ogrenciId);
      await yukle();
      setBilgi(ek ? "Ek ders kaldırıldı." : "Telafi kaldırıldı; hak iade edildi.");
    } catch (e) {
      setHata(hataMesaji(e));
    } finally {
      setMesgul(false);
    }
  }

  const geriYol = tur ? ozet : "/ogrencilerim";
  const geriEtiket = tur ? "← Geri" : "← Öğrencilerim";
  const baslik = ad?.ad ?? "Ders planla";

  return (
    <div>
      <div>
        <Link to={geriYol} className="inline-flex items-center min-h-11 md:min-h-0 text-[13px] text-metin-soluk hover:text-metin">{geriEtiket}</Link>
      </div>
      <SayfaBasligi baslik={baslik} aciklama={ad ? ad.gruplar.join(", ") : undefined} />
      {hata && <p role="alert" className={`${hataKutusu} mb-4`}>{hata}</p>}
      {bilgi && !tur && <p role="status" className={`${basariKutusu} mb-4`}>{bilgi}</p>}

      {tur ? (
        <div className="max-w-3xl">
        <Kart baslik={telafiBasligi(tasinan, tur)}>
          {tasinanId && d === null ? (
            !hata && <p className="text-sm text-metin-soluk">Yükleniyor…</p>
          ) : (
            <TelafiAdaylari
              ogrenciId={ogrenciId}
              tur={tur}
              sonKullanma={d?.son_kullanma ?? null}
              tasinan={tasinan}
              onTamam={() => {
                void yukle();
                setBilgi(tasinan ? "Plan taşındı." : tur === "ek_ders" ? "Ek ders eklendi." : "Telafi planlandı.");
                gezin(ozet, { replace: true });
              }}
            />
          )}
        </Kart>
        </div>
      ) : d === null ? (
        !hata && <p className="text-sm text-metin-soluk">Yükleniyor…</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-3 lg:items-start">
          <div className="space-y-4 lg:col-span-1">
          <Kart baslik="Telafi hakkı">
            {d.kullanilabilir > 0 ? (
              <>
                <div className="font-display text-[32px] leading-[1.15]"><span className="num">{d.kullanilabilir}</span> <span className="text-[17px] text-metin-soluk">telafi planlanabilir</span></div>
                {d.son_kullanma && <p className="num mt-1 text-sm text-metin-soluk">Son gün {tarihBicimle(d.son_kullanma)}</p>}
              </>
            ) : (
              <p className="text-sm text-metin-soluk">Telafi hakkı yok</p>
            )}
          </Kart>

          <div className="grid grid-cols-1 min-[420px]:grid-cols-2 lg:grid-cols-1 gap-2">
            <button className={`${birincilDugme} min-h-11`} disabled={mesgul || d.kullanilabilir <= 0} onClick={() => adimaGit("telafi")}>Telafi planla</button>
            <button className={`${birincilDugme} min-h-11`} disabled={mesgul} onClick={() => adimaGit("ek-ders")}>Ek ders ekle</button>
          </div>
          {d.kullanilabilir <= 0 && <p className="text-xs text-metin-soluk">Planlanabilir telafi hakkı yok.</p>}
          </div>

          <div className="lg:col-span-2">
          <Kart baslik="Planlı dersler">
            {d.planlar.length === 0 ? (
              <p className="text-sm text-metin-soluk">Planlı telafi veya ek ders yok.</p>
            ) : (
              <ul className="space-y-2">
                {d.planlar.map((p) => (
                  <li key={p.oturum_id} className="rounded-[10px] border border-cizgi px-3 py-2.5 text-sm md:flex md:items-center md:justify-between md:gap-4">
                    <div>
                    <div className="num font-medium">{gunMetni(p.tarih)} · {saat(p.baslangic)}–{saat(p.bitis)}</div>
                    <div className="text-metin-soluk flex flex-wrap items-center gap-2">
                      {p.grup.ad}
                      <span className={p.tur === "ek_ders" ? rozetBirincil : rozetUyari}>{p.tur === "ek_ders" ? "Ek ders" : "Telafi"}</span>
                    </div>
                    </div>
                    {p.iptal_edilebilir && p.yoklama === null && (
                      <div className="mt-2 grid grid-cols-2 gap-2 md:mt-0 md:flex md:shrink-0">
                        <button className={`${dugme} min-h-11`} disabled={mesgul} onClick={() => adimaGit(p.tur === "ek_ders" ? "ek-ders" : "telafi", p.oturum_id)}>Taşı</button>
                        <button className={`${dugme} min-h-11`} disabled={mesgul} onClick={() => void kaldir(p)}>Kaldır</button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Kart>
          </div>
        </div>
      )}
    </div>
  );
}
