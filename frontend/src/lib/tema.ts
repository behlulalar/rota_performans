import { useCallback, useSyncExternalStore } from "react";

export type Tema = "light" | "dark";

const ANAHTAR = "rota-tema-2";
const dinleyiciler = new Set<() => void>();

function oku(): Tema {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

function abone(fn: () => void) {
  dinleyiciler.add(fn);
  return () => {
    dinleyiciler.delete(fn);
  };
}

export function temaAyarla(t: Tema) {
  document.documentElement.dataset.theme = t;
  try {
    localStorage.setItem(ANAHTAR, t);
  } catch {
    /* depolama kapalı olabilir; tercih yalnızca bu oturumda geçerli olur */
  }
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", t === "light" ? "#fbfaf6" : "#0e0e0f");
  dinleyiciler.forEach((fn) => fn());
}

/** Geçerli tema ve değiştirme işlevi. İlk değer index.html'deki betikten gelir. */
export function useTema() {
  const tema = useSyncExternalStore(abone, oku, () => "dark" as Tema);
  const degistir = useCallback(() => temaAyarla(oku() === "dark" ? "light" : "dark"), []);
  return { tema, degistir };
}
