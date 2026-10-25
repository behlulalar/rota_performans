import { api, apiBlob } from "../lib/api";
import type { OdemeYontemi } from "./odeme";

export { YONTEM_ETIKET } from "./odeme";

export type GelirRaporu = {
  donem: { yil: number; ay: number; baslangic: string; bitis: string };
  ozet: {
    toplam_tahsilat: string;
    odeme_adedi: number;
    ortalama_odeme: string;
    onceki_ay_tahsilat: string;
    degisim_yuzde: number | string | null;
    iptal_edilen_tutar: string;
    iptal_adedi: number;
    indirim_toplami: string;
    ucretsiz_paket_adedi: number;
  };
  bekleyen: { adet: number; tutar: string; gecikmis_adet: number; gecikmis_tutar: string };
  yontem_dagilimi: { yontem: OdemeYontemi; tutar: string; adet: number; yuzde: number | string }[];
  paket_dagilimi: { paket_adi: string; tutar: string; adet: number }[];
  gunluk: { tarih: string; tutar: string; adet: number }[];
  aylik_seri: { yil: number; ay: number; tutar: string; adet: number }[];
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
