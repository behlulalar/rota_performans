import { useState } from "react";
import { apiyeCevir, bicimle, gecerliMi, rakamlaraCevir } from "../lib/telefon";
import { birincilDugme, dugme, uyariKutusu } from "../lib/stil";
import { WhatsAppSimgesi } from "./WhatsAppDugmesi";

// Şifre yalnızca üst bileşenin geçici durumunda yaşar; kapatılınca üst bileşen siler.
export default function GeciciSifreKutusu({
  sifre,
  baslik,
  onKapat,
  uyari = "Bu şifre yalnızca şimdi görünür. Antrenöre güvenli bir yoldan iletin.",
  telefon,
  giris,
}: {
  sifre: string;
  baslik: string;
  onKapat: () => void;
  uyari?: string;
  /** Doluysa ve geçerli bir Türkiye numarasıysa "WhatsApp ile gönder" düğmesi çıkar. */
  telefon?: string | null;
  /** Mesajda gösterilecek kullanıcı adı (giriş). */
  giris?: string | null;
}) {
  const [kopyalandi, setKopyalandi] = useState(false);

  async function kopyala() {
    try {
      await navigator.clipboard.writeText(sifre);
      setKopyalandi(true);
    } catch {
      setKopyalandi(false);
    }
  }

  const rakamlar = rakamlaraCevir(telefon);
  const whatsappLinki = gecerliMi(rakamlar)
    ? `https://wa.me/${(apiyeCevir(rakamlar) ?? "").slice(1)}?text=${encodeURIComponent(
        [
          "Merhaba, Rota Performans Akademi panel giriş bilgileriniz:",
          `Panel: ${window.location.origin}`,
          giris ? `Kullanıcı adı: ${/^[+\d\s()-]+$/.test(giris) ? bicimle(giris) : giris}` : null,
          `Geçici şifre: ${sifre}`,
          "İlk girişte kendi şifrenizi belirlemeniz istenecek. Bu mesajı kimseyle paylaşmayın.",
        ]
          .filter(Boolean)
          .join("\n"),
      )}`
    : null;

  return (
    <div className="fixed inset-0 z-40 bg-black/70 grid place-items-center p-4" role="dialog" aria-modal="true" aria-label={baslik}>
      <div className="w-full max-w-md bg-yuzey border border-cizgi-guclu rounded-[14px] p-4 space-y-4">
        <h2 className="font-display text-[19px] leading-6">{baslik}</h2>
        <div className="flex items-center gap-2">
          <code className="flex-1 min-w-0 break-all rounded-[10px] bg-zemin border border-cizgi-guclu px-3 py-2.5 font-mono text-altin-metin select-all">{sifre}</code>
          <button onClick={() => void kopyala()} className={dugme}>
            {kopyalandi ? "Kopyalandı" : "Kopyala"}
          </button>
        </div>
        <p className={uyariKutusu}>
          {uyari}
        </p>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {whatsappLinki && (
            <a
              href={whatsappLinki}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-[10px] bg-[#25D366] text-black font-medium text-[13px] px-3 min-h-11 hover:brightness-95"
            >
              <WhatsAppSimgesi />
              WhatsApp ile gönder
            </a>
          )}
          <button onClick={onKapat} className={birincilDugme}>Kapat</button>
        </div>
      </div>
    </div>
  );
}
