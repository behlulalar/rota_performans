import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { duyuruGetir, type DuyuruDetayi, type KanalIstatistigi } from "../api/duyuru";
import { DURUM_ETIKET, KANAL_ETIKET, type BildirimDurumu } from "../api/bildirimYonetimi";
import KanalRozetleri from "../components/KanalRozetleri";
import SayfaBasligi from "../components/SayfaBasligi";
import { hataMesaji } from "../lib/dogrulama";
import { kartKutusu, rozetBasari, rozetHata, rozetNotr, rozetUyari } from "../lib/stil";
import { zaman } from "./Duyurular";

const DURUM_ROZET: Record<BildirimDurumu, string> = {
  bekliyor: rozetUyari, gonderildi: rozetBasari, hata: rozetHata, iptal: rozetNotr,
};

function KanalSonucu({ ad, k, tur }: { ad: string; k: KanalIstatistigi; tur: "push" | "whatsapp" }) {
  const sayilar: [BildirimDurumu, number][] = [
    ["bekliyor", k.bekliyor], ["gonderildi", k.gonderildi], ["hata", k.hata], ["iptal", k.iptal],
  ];
  return (
    <div className={`${kartKutusu} p-4 space-y-2`} data-testid={`kanal-sonucu-${tur}`}>
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium">{ad}</h3>
        <span className="text-xs text-metin-soluk num">{k.toplam} alıcı</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {sayilar.map(([d, n]) => (
          <span key={d} className={n > 0 ? DURUM_ROZET[d] : rozetNotr}>
            {DURUM_ETIKET[d]}: <span className="num">{n}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

export default function DuyuruDetay() {
  const { id } = useParams();
  const [d, setD] = useState<DuyuruDetayi | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let iptal = false;
    duyuruGetir(id)
      .then((v) => !iptal && setD(v))
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => { iptal = true; };
  }, [id]);

  if (hata) {
    return (
      <div className="space-y-3">
        <Link to="/duyurular" className="text-[13px] text-metin-soluk hover:text-metin">← Duyurular</Link>
        <p role="alert" className="text-hata">{hata}</p>
      </div>
    );
  }
  if (!d) return <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>;

  return (
    <div className="space-y-5">
      <div>
        <Link to="/duyurular" className="inline-flex items-center min-h-11 md:min-h-0 text-[13px] text-metin-soluk hover:text-metin">← Duyurular</Link>
      </div>
      <SayfaBasligi baslik={d.baslik} aciklama={`${zaman(d.olusturma)} · ${d.hedef_ozet}`} />
      <div className={`${kartKutusu} p-4 space-y-3`}>
        <p className="text-sm whitespace-pre-wrap break-words" data-testid="duyuru-metni">{d.metin}</p>
        <KanalRozetleri d={d} />
      </div>

      <section>
        <h2 className="font-display text-[19px] mb-2">Kanal sonuçları</h2>
        {!d.kanallar.push && !d.kanallar.whatsapp ? (
          <p className="text-[13px] text-metin-soluk">Kanal seçilmemiş.</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {d.kanallar.push && <KanalSonucu ad="Uygulama bildirimi" k={d.istatistik.push} tur="push" />}
            {d.kanallar.whatsapp && <KanalSonucu ad="WhatsApp" k={d.istatistik.whatsapp} tur="whatsapp" />}
          </div>
        )}
        {d.kanallar.push && d.kanallar.whatsapp && (
          <p className="mt-2 text-xs text-metin-soluk">
            {d.her_iki_kanal
              ? "Her iki kanaldan gönderildi: uygulama bildirimi alan velilere de WhatsApp gitti."
              : "Uygulama bildirimi ulaşan velilere WhatsApp gönderilmez; bu satırlar WhatsApp'ta \"İptal\" görünür."}
          </p>
        )}
      </section>

      <section>
        <h2 className="font-display text-[19px] mb-2">Alıcılar</h2>
        {d.alicilar.length === 0 ? (
          <p className="text-[13px] text-metin-soluk">Alıcı yok.</p>
        ) : (
          <ul className={`${kartKutusu} divide-y divide-cizgi`} aria-label="Alıcılar">
            {d.alicilar.map((a) => (
              <li key={a.bildirim_id} className="px-4 py-2.5 flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
                <div className="min-w-0">
                  <div className="text-sm font-medium">{a.ogrenci_ad}</div>
                  <div className="text-xs text-metin-soluk">{a.alici_ad}</div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className={rozetNotr}>{KANAL_ETIKET[a.kanal]}</span>
                  <span className={DURUM_ROZET[a.durum]}>{DURUM_ETIKET[a.durum]}</span>
                  {a.hata && <span className="text-xs text-hata">Hata: {a.hata}</span>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
