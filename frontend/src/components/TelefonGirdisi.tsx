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
        className="num min-w-0 flex-1 bg-transparent px-3 min-h-[calc(2.75rem-2px)] py-1.5 text-sm"
        // Odak çerçevesi dış kutuda (focus-within) gösterilir; genel :focus-visible kuralını ezmek için satır içi.
        style={{ outline: "none" }}
      />
      {/* Ülke kodu: görünen kısım yalnız "+90"; asıl <select> şeffaf biçimde üstüne biner (liste ülke adlarını gösterir). */}
      <div className="order-first relative shrink-0 flex items-center gap-1 pl-3 pr-2.5 border-r border-cizgi rounded-l-[10px] hover:bg-yuzey-yuksek/50">
        <span aria-hidden="true" className="num text-sm text-metin-orta">+{kod}</span>
        <svg aria-hidden="true" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-metin-soluk">
          <path d="m6 9 6 6 6-6" />
        </svg>
        <select
          aria-label="Ülke kodu"
          value={kod}
          onChange={ulkeDegisti}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer text-sm"
          style={{ backgroundImage: "none", paddingRight: 0 }}
        >
          {secenekler.map((u) => (
            <option key={u.kod} value={u.kod}>
              +{u.kod} {u.ad}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
