import { useEffect, useState } from "react";
import { whatsappBaglan, whatsappGetir, whatsappKes, type WhatsAppBaglanti } from "../api/whatsapp";
import { hataMesaji } from "../lib/dogrulama";
import { bicimle } from "../lib/telefon";
import { birincilDugme, dugme, hataKutusu, rozetBasari, rozetNotr, rozetUyari, uyariKutusu } from "../lib/stil";
import Kart from "./Kart";
import { useOnay } from "./OnayPenceresi";

const DURUM_KONTROL_MS = 3000;
// Evolution'ın QR'ı yaklaşık 40 sn geçerli; süresi dolmadan yenilenir.
const QR_YENILE_MS = 30000;

const ROZET: Record<WhatsAppBaglanti["durum"], [string, string]> = {
  yapilandirilmadi: [rozetNotr, "Kurulmadı"],
  ulasilamiyor: [rozetUyari, "Servise ulaşılamıyor"],
  bagli_degil: [rozetNotr, "Bağlı değil"],
  baglaniyor: [rozetUyari, "QR bekleniyor"],
  bagli: [rozetBasari, "Bağlı"],
};

/** Ayarlar > WhatsApp bağlantısı: kulüp numarasını QR okutarak bağlar, durumu izler, bağlantıyı keser. */
export default function WhatsAppBaglantisi() {
  const onayla = useOnay();
  const [b, setB] = useState<WhatsAppBaglanti | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const qrAcik = b?.durum === "baglaniyor" && !!b.qr;

  useEffect(() => {
    whatsappGetir().then(setB, (e) => setHata(hataMesaji(e)));
  }, []);

  // QR ekrandayken: durum sık sık yoklanır (okutulunca "Bağlı"ya geçer), QR süresi dolmadan yenilenir.
  useEffect(() => {
    if (!qrAcik) return;
    const durum = setInterval(() => {
      whatsappGetir().then((y) => y.durum === "bagli" && setB(y), () => {});
    }, DURUM_KONTROL_MS);
    const yenile = setInterval(() => {
      whatsappBaglan().then(setB, () => {});
    }, QR_YENILE_MS);
    return () => {
      clearInterval(durum);
      clearInterval(yenile);
    };
  }, [qrAcik]);

  async function calistir(is: () => Promise<WhatsAppBaglanti>) {
    setMesgul(true);
    setHata(null);
    try {
      setB(await is());
    } catch (e) {
      setHata(hataMesaji(e));
    } finally {
      setMesgul(false);
    }
  }

  async function kes() {
    const bagli = b?.durum === "bagli";
    if (bagli && !(await onayla({
      baslik: "WhatsApp bağlantısı kesilsin mi?",
      mesaj: "Kulüp numarası sistemden çıkarılır, WhatsApp mesajları gönderilemez. Yeniden bağlamak için QR kodu tekrar okutmanız gerekir.",
      onayYazisi: "Bağlantıyı kes",
      tehlikeli: true,
    }))) return;
    await calistir(whatsappKes);
  }

  const [rozet, rozetYazi] = b ? ROZET[b.durum] : [rozetNotr, "…"];

  return (
    <Kart baslik="WhatsApp bağlantısı" aciklama="Velilere WhatsApp mesajı gönderecek kulüp numarası" sag={<span className={rozet}>{rozetYazi}</span>}>
      <div className="space-y-4">
        {hata && <p role="alert" className={hataKutusu}>{hata}</p>}

        {b?.durum === "yapilandirilmadi" && (
          <p className="text-sm text-metin-soluk">WhatsApp servisi sunucuda henüz kurulmadı. Teknik destekle iletişime geçin.</p>
        )}
        {b?.durum === "ulasilamiyor" && (
          <p className={uyariKutusu}>WhatsApp servisine şu an ulaşılamıyor. Birkaç dakika sonra tekrar deneyin; sürerse teknik destekle iletişime geçin.</p>
        )}

        {b?.durum === "bagli" && (
          <>
            <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
              <dt className="text-metin-soluk">Numara</dt><dd className="num font-medium">{b.numara ? bicimle(b.numara) : "—"}</dd>
              <dt className="text-metin-soluk">Profil adı</dt><dd>{b.profil_adi || "—"}</dd>
            </dl>
            <button type="button" className={dugme} disabled={mesgul} onClick={() => void kes()}>Bağlantıyı kes</button>
          </>
        )}

        {(b?.durum === "bagli_degil" || (b?.durum === "baglaniyor" && !b.qr)) && (
          <>
            <ol className="text-sm text-metin-soluk list-decimal pl-5 space-y-1">
              <li>Kulübe ait, kişisel kullanılmayan numaranın telefonunda WhatsApp'ı açın.</li>
              <li><span className="text-metin">Ayarlar › Bağlı cihazlar › Cihaz bağla</span> adımlarını izleyin.</li>
              <li>Aşağıdaki düğmeye basıp ekrana gelen QR kodu okutun.</li>
            </ol>
            <button type="button" className={birincilDugme} disabled={mesgul} onClick={() => void calistir(whatsappBaglan)}>
              {mesgul ? "QR hazırlanıyor…" : "QR kodu oluştur"}
            </button>
          </>
        )}

        {qrAcik && (
          <>
            <div className="flex flex-col sm:flex-row gap-5 items-center sm:items-start">
              <img src={b.qr!} alt="WhatsApp bağlantı QR kodu" className="size-56 shrink-0 rounded-[10px] bg-white p-2 border border-cizgi" />
              <div className="text-sm space-y-2">
                <p className="font-medium">Telefonunuzla QR kodu okutun</p>
                <p className="text-metin-soluk">WhatsApp › Ayarlar › Bağlı cihazlar › Cihaz bağla. Kod 30 saniyede bir kendiliğinden yenilenir; okutunca bu kart "Bağlı" olarak güncellenir.</p>
              </div>
            </div>
            <button type="button" className={dugme} disabled={mesgul} onClick={() => void kes()}>Vazgeç</button>
          </>
        )}
      </div>
    </Kart>
  );
}
