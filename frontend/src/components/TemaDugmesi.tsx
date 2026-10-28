import { useTema } from "../lib/tema";
import Simge from "./Simge";

/** `serit` koyu şerit üzerinde, `normal` sayfa zemininde kullanılır. */
export default function TemaDugmesi({ gorunum = "normal", sinif = "", etiket = false }: { gorunum?: "normal" | "serit"; sinif?: string; etiket?: boolean }) {
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
      className={`${
        etiket ? "flex flex-col items-center justify-center gap-1 w-16 h-14 rounded-lg hover:bg-white/5" : "grid place-items-center size-11 rounded-[10px]"
      } transition-colors ${renk} ${sinif}`}
    >
      <Simge ad={tema === "dark" ? "gunes" : "ay"} />
      {etiket && <span className="text-[11px] leading-none font-medium">{tema === "dark" ? "Açık tema" : "Koyu tema"}</span>}
    </button>
  );
}
