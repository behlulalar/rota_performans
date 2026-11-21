import { useEffect, useState } from "react";
import { ekDersAdaylariGetir, telafiAdaylariGetir, type TelafiAdayi, type TelafiPlani } from "../api/ogrenci";
import { ekDersEkle, telafiPlanla } from "../api/takvim";
import { hataMesaji, tarihBicimle } from "../lib/dogrulama";
import { bugun, gunEkle, tarihCoz, yyyyAyGun } from "../lib/tarih";
import { dugme } from "../lib/stil";

export const gunMetni = (s: string) => tarihCoz(s).toLocaleDateString("tr-TR", { day: "numeric", month: "long", weekday: "long" });
export const saat = (s: string) => s.slice(0, 5);

/** Ortak pencere (yönetici). */
export function Pencere({ baslik, onKapat, children }: { baslik: string; onKapat: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-30 bg-black/70 grid place-items-center p-4" role="dialog" aria-modal="true" aria-label={baslik}>
      <div className="w-full max-w-md flex flex-col bg-yuzey border border-cizgi-guclu max-h-full rounded-[14px] overflow-hidden">
        <div className="flex items-center justify-between px-4 min-h-11 border-b border-cizgi shrink-0">
          <h2 className="font-display text-[19px] leading-6 min-w-0">{baslik}</h2>
          <button onClick={onKapat} className="px-2 min-h-11 text-[13px] text-metin-soluk hover:text-metin" aria-label="Kapat">Kapat</button>
        </div>
        <div className="p-4 overflow-y-auto min-h-0 flex-1">{children}</div>
      </div>
    </div>
  );
}

type Icerik = {
  ogrenciId: string;
  sonKullanma: string | null;
  /** Verilirse "Taşı" kipi: seçilen derse planlanırken bu plan aynı işlemde silinir. */
  tasinan?: TelafiPlani;
  /** Varsayılan "telafi". "ek_ders": ücretsiz, ders hakkı bilgisi yok. */
  tur?: "telafi" | "ek_ders";
  onTamam: () => void;
};
type Props = Icerik & { onKapat: () => void };

export const telafiBasligi = (tasinan?: TelafiPlani, tur: "telafi" | "ek_ders" = "telafi") =>
  tur === "ek_ders" ? (tasinan ? "Ek dersi taşı" : "Ek ders ekle") : tasinan ? "Telafiyi taşı" : "Telafi planla";

/** Telafi planlama / taşıma penceresi (yönetici ve antrenör ortak). Adaylar 14 günlüktür. */
export default function TelafiPlanla({ onKapat, ...r }: Props) {
  return (
    <Pencere baslik={telafiBasligi(r.tasinan, r.tur)} onKapat={onKapat}>
      <TelafiAdaylari {...r} />
    </Pencere>
  );
}

/** Aday listesi: yönetici penceresinde ve antrenör planlama sayfasında ortak. */
export function TelafiAdaylari({ ogrenciId, sonKullanma, tasinan, tur = "telafi", onTamam }: Icerik) {
  const ek = tur === "ek_ders";
  const [adaylar, setAdaylar] = useState<TelafiAdayi[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);

  useEffect(() => {
    let iptal = false;
    (ek ? ekDersAdaylariGetir : telafiAdaylariGetir)(ogrenciId, bugun(), yyyyAyGun(gunEkle(new Date(), 14)), tasinan?.oturum_id)
      .then((v) => !iptal && setAdaylar(v))
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => { iptal = true; };
  }, [ogrenciId, tasinan?.oturum_id, ek]);

  async function sec(a: TelafiAdayi) {
    setMesgul(true);
    setHata(null);
    try {
      await (ek ? ekDersEkle : telafiPlanla)(a.oturum.id, ogrenciId, tasinan?.oturum_id);
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
      {ek && <p className="mb-3 text-[13px] text-metin-soluk">Ücretsiz, ders hakkını etkilemez.</p>}
      {!ek && sonKullanma && (
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
