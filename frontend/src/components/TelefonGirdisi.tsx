import type { ChangeEvent } from "react";
import { rakamlaraCevir } from "../lib/telefon";

/** Sabit "+90" önekli telefon kutusu. value/onChange yalnızca 10 haneye kadar rakam dizisidir. */
export default function TelefonGirdisi({
  value,
  onChange,
  autoFocus,
  ...aria
}: {
  value: string;
  onChange: (rakamlar: string) => void;
  autoFocus?: boolean;
  id?: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
}) {
  function degisti(e: ChangeEvent<HTMLInputElement>) {
    onChange(rakamlaraCevir(e.target.value));
  }
  return (
    <div className="mt-1 flex items-stretch w-full rounded-[10px] bg-zemin border border-cizgi-guclu focus-within:border-altin">
      <span aria-hidden="true" className="flex items-center pl-3 pr-2 text-sm text-metin-soluk select-none">+90</span>
      <input
        {...aria}
        type="tel"
        inputMode="numeric"
        autoComplete="off"
        autoFocus={autoFocus}
        placeholder="5XX XXX XX XX"
        value={value}
        onChange={degisti}
        className="num min-w-0 flex-1 bg-transparent pr-3 min-h-11 py-1.5 text-sm outline-none"
      />
    </div>
  );
}
