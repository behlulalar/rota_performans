import { useEffect, useState, type ChangeEvent } from "react";
import { enFazlaUlusal, numaraCoz, ULKELER, ulkeAyir, VARSAYILAN_ULKE } from "../lib/telefon";

/**
 * Ülke kodu seçilebilen telefon kutusu. Ülke kodu varsayılan olarak "+90"dır; yurt dışından gelenler listeden
 * değiştirebilir. value/onChange "tam numara"dır ("+905321234567"); ulusal numara boşsa değer boş dizedir.
 * Türkiye için 10, diğer ülkelerde en fazla 15 − ülke kodu hane girilebilir.
 * Numara kutusu DOM'da önce gelir (etiket ona bağlansın); ülke seçici CSS ile solda görünür.
 */
export default function TelefonGirdisi({
  value,
  onChange,
  autoFocus,
  ...aria
}: {
  value: string;
  onChange: (tam: string) => void;
  autoFocus?: boolean;
  id?: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
}) {
  const [kod, setKod] = useState(() => ulkeAyir(value).kod);
  const { kod: degerKodu, ulusal } = ulkeAyir(value);

  // Dışarıdan numara gelirse (form yüklenince, "başka hesap" vb.) ülke kodu ona uyar; boşken seçim korunur.
  useEffect(() => {
    if (value) setKod(degerKodu);
  }, [value, degerKodu]);

  const secenekler = ULKELER.some((u) => u.kod === kod) ? ULKELER : [...ULKELER, { kod, iso: "", ad: "Diğer" }];
  const turkiye = kod === VARSAYILAN_ULKE;

  function yaz(ulusalYeni: string, yeniKod = kod) {
    const r = ulusalYeni.replace(/\D/g, "").slice(0, enFazlaUlusal(yeniKod));
    onChange(r ? `+${yeniKod}${r}` : "");
  }

  function degisti(e: ChangeEvent<HTMLInputElement>) {
    const ham = e.target.value;
    // Yapıştırılan tam numara (+49 151… / 0532… / 90532…) ülke koduyla birlikte çözülür.
    if (ham.trim().startsWith("+") || /^(0|90)\d{9,}/.test(ham.replace(/\D/g, ""))) {
      const tam = numaraCoz(ham);
      if (tam) setKod(ulkeAyir(tam).kod);
      onChange(tam);
      return;
    }
    yaz(ham);
  }

  function ulkeDegisti(e: ChangeEvent<HTMLSelectElement>) {
    const yeni = e.target.value;
    setKod(yeni);
    yaz(ulusal, yeni);
  }

  return (
    <div className="mt-1 flex items-stretch w-full rounded-[10px] bg-zemin border border-cizgi-guclu focus-within:border-altin">
      <input
        {...aria}
        type="tel"
        inputMode="numeric"
        autoComplete="off"
        autoFocus={autoFocus}
        placeholder={turkiye ? "5XX XXX XX XX" : "Numara"}
        value={ulusal}
        onChange={degisti}
        className="num min-w-0 flex-1 bg-transparent px-3 min-h-11 py-1.5 text-sm outline-none focus-visible:outline-none"
      />
      <select
        aria-label="Ülke kodu"
        value={kod}
        onChange={ulkeDegisti}
        className="order-first num shrink-0 bg-transparent pl-3 pr-7 bg-[position:right_0.45rem_center] bg-[length:0.9rem] text-sm text-metin-orta outline-none focus-visible:outline-none cursor-pointer border-r border-cizgi min-h-11 rounded-l-[10px]"
      >
        {secenekler.map((u) => (
          <option key={u.kod} value={u.kod} title={u.ad}>
            +{u.kod} {u.iso}
          </option>
        ))}
      </select>
    </div>
  );
}
