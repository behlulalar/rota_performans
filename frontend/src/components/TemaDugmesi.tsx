import { useTema } from "../lib/tema";
import Simge from "./Simge";

/** `serit` koyu şerit üzerinde, `normal` sayfa zemininde kullanılır. */
export default function TemaDugmesi({ gorunum = "normal", sinif = "" }: { gorunum?: "normal" | "serit"; sinif?: string }) {
  const { tema, degistir } = useTema();
  const renk =
    gorunum === "serit"
      ? "text-serit-ikon hover:text-serit-ikon-secili"
      : "text-metin-soluk hover:text-metin border border-cizgi hover:border-cizgi-guclu bg-yuzey";
  return (
    <button
      type="button"
      onClick={degistir}
      aria-label={tema === "dark" ? "Açık temaya geç" : "Koyu temaya geç"}
      title={tema === "dark" ? "Açık temaya geç" : "Koyu temaya geç"}
      className={`grid place-items-center size-11 rounded-[3px] transition-colors ${renk} ${sinif}`}
    >
      <Simge ad={tema === "dark" ? "gunes" : "ay"} />
    </button>
  );
}
