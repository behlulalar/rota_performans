import { useEffect, useState } from "react";
import { telafiAdaylariGetir, type TelafiAdayi, type TelafiPlani } from "../api/ogrenci";
import { telafiPlanla } from "../api/takvim";
import { hataMesaji, tarihBicimle } from "../lib/dogrulama";
import { bugun, gunEkle, tarihCoz, yyyyAyGun } from "../lib/tarih";
import { dugme } from "../lib/stil";

export const gunMetni = (s: string) => tarihCoz(s).toLocaleDateString("tr-TR", { day: "numeric", month: "long", weekday: "long" });
export const saat = (s: string) => s.slice(0, 5);

/** Ortak pencere. `alt`: dar ekranda alttan açılan sayfa (antrenör; alt sekme çubuğunun [z-40] üstünde, z-50), geniş ekranda ortada. */
export function Pencere({ baslik, onKapat, children, alt, geri, altBolum }: {
  baslik: string; onKapat: () => void; children: React.ReactNode; alt?: boolean; geri?: () => void; altBolum?: React.ReactNode;
}) {
  return (
    <div
      className={`fixed inset-0 bg-black/70 grid ${alt ? "z-50 place-items-end sm:place-items-center sm:p-4" : "z-30 place-items-center p-4"}`}
      role="dialog" aria-modal="true" aria-label={baslik}
    >
      <div className={`w-full max-w-md flex flex-col bg-yuzey border border-cizgi-guclu ${alt ? "max-h-[85dvh] rounded-t-[14px] sm:rounded-[14px]" : "max-h-full rounded-[14px]"}`}>
        <div className="flex items-center justify-between px-4 min-h-11 border-b border-cizgi shrink-0">
          <div className="flex items-center gap-1 min-w-0">
            {geri && <button onClick={geri} className="pr-2 min-h-11 text-[13px] text-metin-soluk hover:text-metin">Geri</button>}
            <h2 className="font-display text-[19px] leading-6">{baslik}</h2>
          </div>
          <button onClick={onKapat} className="px-2 min-h-11 text-[13px] text-metin-soluk hover:text-metin" aria-label="Kapat">Kapat</button>
        </div>
        <div className="p-4 overflow-y-auto min-h-0 flex-1">{children}</div>
        {altBolum && <div className="shrink-0 border-t border-cizgi bg-yuzey p-4 pb-[calc(1rem+env(safe-area-inset-bottom))]">{altBolum}</div>}
      </div>
    </div>
  );
}

type Icerik = {
  ogrenciId: string;
  sonKullanma: string | null;
  /** Verilirse "Taşı" kipi: seçilen derse planlanırken bu plan aynı işlemde silinir. */
  tasinan?: TelafiPlani;
  onTamam: () => void;
};
type Props = Icerik & { alt?: boolean; onKapat: () => void; onGeri?: () => void };

export const telafiBasligi = (tasinan?: TelafiPlani) => (tasinan ? "Telafiyi taşı" : "Telafi planla");

/** Telafi planlama / taşıma penceresi (yönetici ve antrenör ortak). Adaylar 14 günlüktür. */
export default function TelafiPlanla({ alt, onKapat, onGeri, ...r }: Props) {
  return (
    <Pencere baslik={telafiBasligi(r.tasinan)} onKapat={onKapat} alt={alt} geri={onGeri}>
      <TelafiAdaylari {...r} />
    </Pencere>
  );
}

/** Aday listesi (pencere içeriği); başka bir pencerenin içinde adım olarak da kullanılır. */
export function TelafiAdaylari({ ogrenciId, sonKullanma, tasinan, onTamam }: Icerik) {
  const [adaylar, setAdaylar] = useState<TelafiAdayi[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);

  useEffect(() => {
    let iptal = false;
    telafiAdaylariGetir(ogrenciId, bugun(), yyyyAyGun(gunEkle(new Date(), 14)), tasinan?.oturum_id)
      .then((v) => !iptal && setAdaylar(v))
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => { iptal = true; };
  }, [ogrenciId, tasinan?.oturum_id]);

  async function sec(a: TelafiAdayi) {
    setMesgul(true);
    setHata(null);
    try {
      await telafiPlanla(a.oturum.id, ogrenciId, tasinan?.oturum_id);
      onTamam();
    } catch (err) {
      setHata(hataMesaji(err));
      setMesgul(false);
    }
  }

  const adaylarListe = tasinan ? (adaylar ?? []).filter((a) => a.oturum.id !== tasinan.oturum_id) : adaylar;

  return (
    <>
      {hata && <p role="alert" className="mb-3 text-sm text-hata">{hata}</p>}
      {tasinan && (
        <p className="mb-3 text-[13px] text-metin-soluk">
          Şu an: <span className="num font-medium text-metin">{gunMetni(tasinan.tarih)} · {saat(tasinan.baslangic)}</span>. Yeni dersi seçin; eski plan kaldırılır.
        </p>
      )}
      {sonKullanma && (
        <p className="mb-3 text-[13px] text-metin-soluk">
          Telafi hakkı <span className="num font-medium text-metin">{tarihBicimle(sonKullanma)}</span> tarihine kadar geçerli.
        </p>
      )}
      {adaylarListe === null ? (
        !hata && <p className="text-sm text-metin-soluk">Yükleniyor…</p>
      ) : adaylarListe.length === 0 ? (
        <p className="text-sm text-metin-soluk">Önümüzdeki 14 günde uygun ders yok</p>
      ) : (
        <ul className="space-y-2">
          {adaylarListe.map((a) => (
            <li key={a.oturum.id} className="rounded-[10px] border border-cizgi px-3 py-2.5 flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm min-w-0">
                <div className="font-medium">{gunMetni(a.oturum.tarih)} · {saat(a.oturum.baslangic)}–{saat(a.oturum.bitis)}</div>
                <div className="text-metin-soluk">
                  {a.oturum.grup.ad}{a.oturum.antrenor ? ` · ${a.oturum.antrenor.ad_soyad}` : ""} · {a.bos_yer} boş yer
                </div>
              </div>
              <button className={`${dugme} min-h-11`} disabled={mesgul} aria-label={`Seç: ${a.oturum.grup.ad} ${a.oturum.tarih}`} onClick={() => void sec(a)}>Seç</button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
