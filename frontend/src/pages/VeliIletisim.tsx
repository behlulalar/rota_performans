import { useEffect, useState, type ReactNode } from "react";
import { iletisimGetir, type KulupIletisim } from "../api/ayarlar";
import Kart from "../components/Kart";
import SayfaBasligi from "../components/SayfaBasligi";
import Simge, { type SimgeAdi } from "../components/Simge";
import { WhatsAppSimgesi } from "../components/WhatsAppDugmesi";
import { hataMesaji } from "../lib/dogrulama";
import { bicimle, rakamlaraCevir, whatsappAdresi } from "../lib/telefon";
import { hataKutusu } from "../lib/stil";

/** Tıklanabilir iletişim satırı: simge, soluk etiket, altında değer. */
function Satir({ simge, etiket, deger, href, yeniSekme }: { simge: ReactNode; etiket: string; deger: string; href: string; yeniSekme?: boolean }) {
  return (
    <a
      href={href}
      {...(yeniSekme ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      className="flex items-center gap-4 px-5 min-h-[68px] border-t border-cizgi first:border-t-0 hover:bg-yuzey-yuksek transition-colors"
    >
      <span className="grid place-items-center size-10 shrink-0 rounded-full bg-altin/15 text-altin-metin">{simge}</span>
      <span className="min-w-0 flex-1">
        <span className="block text-[13px] text-metin-soluk">{etiket}</span>
        <span className="block font-medium break-words">{deger}</span>
      </span>
      <Simge ad="ileri" boyut={16} sinif="text-metin-soluk shrink-0" />
    </a>
  );
}

const simge = (ad: SimgeAdi) => <Simge ad={ad} boyut={18} />;

export default function VeliIletisim() {
  const [k, setK] = useState<KulupIletisim | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    iletisimGetir().then(setK, (e) => setHata(hataMesaji(e)));
  }, []);

  const whatsapp = whatsappAdresi(k?.telefon);
  const bos = k && !k.telefon && !k.eposta && !k.adres;

  return (
    <>
      <SayfaBasligi baslik="Bize ulaşın" aciklama={k ? k.ad : undefined} />
      {hata && <div className={hataKutusu}>{hata}</div>}
      {bos && <Kart><p className="text-sm text-metin-soluk">Kulüp iletişim bilgileri henüz eklenmedi.</p></Kart>}
      {k && !bos && (
        <Kart bosluksuz sinif="max-w-xl">
          {k.telefon && <Satir simge={simge("telefon")} etiket="Telefon · Aramak için dokunun" deger={bicimle(k.telefon)} href={`tel:+90${rakamlaraCevir(k.telefon)}`} />}
          {whatsapp && <Satir simge={<WhatsAppSimgesi />} etiket="WhatsApp · Mesaj yazın" deger={bicimle(k.telefon)} href={whatsapp} yeniSekme />}
          {k.eposta && <Satir simge={simge("eposta")} etiket="E-posta" deger={k.eposta} href={`mailto:${k.eposta}`} />}
          {k.adres && (
            <Satir
              simge={simge("konum")}
              etiket="Adres · Haritada açın"
              deger={k.adres}
              href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(k.adres)}`}
              yeniSekme
            />
          )}
        </Kart>
      )}
    </>
  );
}
