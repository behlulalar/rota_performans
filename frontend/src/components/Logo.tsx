/**
 * Marka işareti. Kulübün gerçek logosu gelince yalnızca bu dosya değişir:
 * `RP` yerine görsel konur, tüm ekranlar (giriş, üst çubuk, menü) kendiliğinden güncellenir.
 */
export default function Logo({ sinif = "size-9 text-xs" }: { sinif?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`${sinif} shrink-0 rounded-[8px] bg-serit border border-altin grid place-items-center text-altin font-semibold tracking-wider`}
    >
      RP
    </span>
  );
}
