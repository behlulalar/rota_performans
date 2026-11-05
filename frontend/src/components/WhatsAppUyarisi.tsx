import { useEffect, useState } from "react";
import { whatsappGetir, type WhatsAppBaglanti } from "../api/whatsapp";
import { uyariKutusu } from "../lib/stil";

/** WhatsApp etkinken (kurulmuşken) bağlantı sorunu varsa kısa uyarı metni; sorun yoksa null. */
export function whatsappUyarisi(b: WhatsAppBaglanti | null): string | null {
  if (!b || b.durum === "yapilandirilmadi") return null;
  if (b.devre_kesici.acik) {
    return `WhatsApp gönderimi durduruldu${b.devre_kesici.sebep ? `: ${b.devre_kesici.sebep}` : "."}${
      b.devre_kesici.sebep && !b.devre_kesici.sebep.endsWith(".") ? "." : ""
    } Gönderim yaklaşık 30 dakika sonra bağlantı sağlıklıysa kendiliğinden yeniden başlar.`;
  }
  if (b.durum === "ulasilamiyor") return "WhatsApp servisine ulaşılamıyor; bekleyen mesajlar servis dönünce gönderilir.";
  if (b.durum !== "bagli") return "WhatsApp bağlı değil; WhatsApp mesajları gönderilmiyor, bekleyenler bağlanınca gider.";
  return null;
}

/** WhatsApp durumunu bir kez yükler (yönetici yetkisi gerekir); hata durumunda sessizce null kalır. */
export function useWhatsAppDurumu(): WhatsAppBaglanti | null {
  const [b, setB] = useState<WhatsAppBaglanti | null>(null);
  useEffect(() => {
    let iptal = false;
    whatsappGetir().then((v) => !iptal && setB(v), () => undefined);
    return () => { iptal = true; };
  }, []);
  return b;
}

/** Yönetici panellerinde küçük WhatsApp uyarısı; yalnız WhatsApp kurulmuşsa ve sorun varsa görünür. */
export default function WhatsAppUyarisi({ b, sinif = "" }: { b: WhatsAppBaglanti | null; sinif?: string }) {
  const m = whatsappUyarisi(b);
  if (!m) return null;
  return <p role="status" data-testid="whatsapp-uyarisi" className={`${uyariKutusu} ${sinif}`}>{m}</p>;
}
