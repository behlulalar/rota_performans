import { api, apiBlob } from "../lib/api";
import type { OdemeYontemi } from "./odeme";

export { YONTEM_ETIKET } from "./odeme";

export type GelirRaporu = {
  donem: { yil: number; ay: number; baslangic: string; bitis: string };
  ozet: {
    toplam_tahsilat: string | null;
    odeme_adedi: number;
    ortalama_odeme: string | null;
    manuel_gelir: string | null;
    manuel_gider: string | null;
    manuel_adedi: number;
    net_gelir: string | null;
    onceki_ay_tahsilat: string | null;
    onceki_ay_net: string | null;
    degisim_yuzde: number | string | null;
    iptal_edilen_tutar: string | null;
    iptal_adedi: number;
    indirim_toplami: string | null;
    ucretsiz_paket_adedi: number;
  };
  bekleyen: { adet: number; tutar: string | null; gecikmis_adet: number; gecikmis_tutar: string | null };
  yontem_dagilimi: { yontem: OdemeYontemi; tutar: string | null; adet: number; yuzde: number | string | null }[];
  paket_dagilimi: { paket_adi: string; tutar: string | null; adet: number }[];
  gunluk: { tarih: string; tutar: string | null; adet: number }[];
  aylik_seri: { yil: number; ay: number; tutar: string | null; adet: number }[];
};

export const gelirRaporuGetir = (yil: number, ay: number) =>
  api<GelirRaporu>(`/api/raporlar/gelir?${new URLSearchParams({ yil: String(yil), ay: String(ay) })}`);

/** CSV'yi yetkili istekle blob olarak indirir ve tarayıcıdan kaydettirir. Dosya adını döner. */
export async function gelirCsvIndir(baslangic: string, bitis: string): Promise<string> {
  const blob = await apiBlob(`/api/raporlar/gelir.csv?${new URLSearchParams({ baslangic, bitis })}`);
  const ad = `gelir-${baslangic}_${bitis}.csv`;
  const adres = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = adres;
  a.download = ad;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(adres), 1000);
  return ad;
}
