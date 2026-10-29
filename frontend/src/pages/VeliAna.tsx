import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { cocuklarimiGetir, type CocukOzet, type VeliDers } from "../api/veli";
import { useAuth } from "../auth/AuthProvider";
import Kart from "../components/Kart";
import OgrenciFoto from "../components/OgrenciFoto";
import SayfaBasligi from "../components/SayfaBasligi";
import { hataMesaji } from "../lib/dogrulama";
import { saat } from "../lib/program";
import { rozetNotr, rozetUyari } from "../lib/stil";
import { tarihCoz } from "../lib/tarih";

export const dersMetni = (d: VeliDers) =>
  `${tarihCoz(d.tarih).toLocaleDateString("tr-TR", { day: "numeric", month: "long", weekday: "long" })} · ${saat(d.baslangic)}–${saat(d.bitis)}`;

function CocukKarti({ c }: { c: CocukOzet }) {
  const h = c.ders_hakki;
  return (
    <Link
      to={`/panel/cocuk/${c.id}`}
      className="block bg-yuzey border border-cizgi rounded-[14px] p-5 hover:border-altin transition-colors"
    >
      <div className="flex items-center gap-4">
        <OgrenciFoto id={c.id} fotoVar={c.foto_var} ad={c.ad} soyad={c.soyad} boyut="kucuk" sinif="size-14 rounded-full" veli />
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-[22px] leading-[1.2] break-words">
            {c.ad} {c.soyad}
          </h2>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {c.durum === "pasif" && <span className={rozetNotr}>Pasif</span>}
            {c.gruplar.map((g) => (
              <span key={g.id} className={rozetNotr}>
                {g.ad}
              </span>
            ))}
            {c.odeme_bekleyen > 0 && <span className={rozetUyari}>Ödeme bekliyor</span>}
            {c.ders_hakki_bitti && <span className={rozetUyari}>Ders hakkı bitti</span>}
          </div>
        </div>
      </div>

      <dl className="mt-5 grid grid-cols-2 gap-px bg-cizgi border border-cizgi rounded-[10px] overflow-hidden">
        <div className="bg-yuzey px-4 py-3">
          <dt className="text-[11px] font-semibold uppercase tracking-[0.12em] text-metin-soluk">Kalan ders</dt>
          <dd className="num font-display text-[26px] leading-[1.15] mt-1">{Math.max(0, h.normal)}</dd>
        </div>
        <div className="bg-yuzey px-4 py-3">
          <dt className="text-[11px] font-semibold uppercase tracking-[0.12em] text-metin-soluk">Telafi hakkı</dt>
          <dd className="num font-display text-[26px] leading-[1.15] mt-1">{Math.max(0, h.kullanilabilir_telafi)}</dd>
        </div>
      </dl>

      <p className="num mt-4 text-sm text-metin-soluk">
        {c.siradaki_ders ? (
          <>
            <span className="font-medium text-metin">Sıradaki ders:</span> {dersMetni(c.siradaki_ders)}
            {c.siradaki_ders.telafi_mi && " (telafi)"}
          </>
        ) : (
          "Planlanmış yaklaşan ders yok."
        )}
      </p>
    </Link>
  );
}

export default function VeliAna() {
  const { kullanici } = useAuth();
  const [liste, setListe] = useState<CocukOzet[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    let iptal = false;
    cocuklarimiGetir()
      .then((v) => !iptal && setListe(v))
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => {
      iptal = true;
    };
  }, []);

  // Tek öğrenci varsa doğrudan onun sayfası açılır (reşit öğrenci ve tek çocuklu veli).
  if (liste?.length === 1) return <Navigate to={`/panel/cocuk/${liste[0].id}`} replace />;

  const veli = kullanici?.rol === "veli";
  return (
    <>
      <SayfaBasligi
        baslik={veli ? "Çocuklarım" : "Bilgilerim"}
        aciklama={veli ? "Kalan ders, program ve ödeme durumları" : undefined}
      />
      {hata && (
        <p role="alert" className="text-sm text-hata">
          {hata}
        </p>
      )}
      {liste === null && !hata && (
        <div role="status" aria-label="Yükleniyor" className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1].map((i) => (
            <div key={i} aria-hidden="true" className="animate-pulse rounded-[14px] bg-yuzey-yuksek h-56" />
          ))}
        </div>
      )}
      {liste?.length === 0 && (
        <Kart baslik="Bağlı öğrenci yok">
          <p className="text-sm text-metin-soluk">
            Hesabınıza henüz bir öğrenci bağlanmamış. Lütfen kulüple iletişime geçin.
          </p>
        </Kart>
      )}
      {liste && liste.length > 1 && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {liste.map((c) => (
            <CocukKarti key={c.id} c={c} />
          ))}
        </div>
      )}
    </>
  );
}
