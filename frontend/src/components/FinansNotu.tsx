import { useAuth } from "../auth/AuthProvider";

/** Teknik destek hesabında sunucu tutarları null döner ve finansal işlemler kapalıdır; arayüz bu bilgiyle düğmeleri gizler. */
export const useTutarGizli = () => useAuth().kullanici?.rol === "destek";

/** Finans sayfalarının başındaki küçük bilgi notu; yalnız teknik destek hesabında görünür. */
export default function FinansNotu() {
  if (!useTutarGizli()) return null;
  return <p className="text-xs text-metin-soluk mb-4" data-testid="finans-notu">Tutarlar teknik destek hesabında gizlenir.</p>;
}
