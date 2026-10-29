import amblem from "../assets/logo-amblem.png";

/**
 * Kulüp amblemi (kanatlı R ve pusula). Şeffaf altın PNG olduğundan siyah marka çubuğu üzerinde kullanılır.
 * `sinif` yüksekliği belirler, genişlik oranla uyar.
 */
export default function Logo({ sinif = "h-11" }: { sinif?: string }) {
  return <img src={amblem} alt="" aria-hidden="true" className={`${sinif} w-auto shrink-0 select-none`} draggable={false} />;
}
