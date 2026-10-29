import type { SimgeAdi } from "../components/Simge";

export type MenuOgesi = {
  ad: string;
  simge: SimgeAdi;
  /** Yoksa öğe henüz yapılmamıştır: pasif ve "Yakında" etiketli. */
  yol?: string;
  /** Aynı öğeyi etkin sayan ek yol önekleri (ör. yoklama ekranı takvimin parçasıdır). */
  ekYollar?: string[];
};
export type MenuBolumu = { anahtar: string; ad: string; simge: SimgeAdi; ogeler: MenuOgesi[] };

const TAKVIM: MenuOgesi = { ad: "Takvim", simge: "takvim", yol: "/takvim", ekYollar: ["/oturum"] };

export const YONETICI_MENUSU: MenuBolumu[] = [
  {
    anahtar: "genel",
    ad: "Genel",
    simge: "genel",
    ogeler: [{ ad: "Genel bakış", simge: "genel", yol: "/genel-bakis" }, TAKVIM],
  },
  {
    anahtar: "kayitlar",
    ad: "Kayıtlar",
    simge: "kayit",
    ogeler: [
      { ad: "Öğrenciler", simge: "kayit", yol: "/ogrenciler" },
      { ad: "Antrenörler", simge: "antrenor", yol: "/antrenorler" },
      { ad: "Gruplar", simge: "grup", yol: "/gruplar" },
    ],
  },
  {
    anahtar: "finans",
    ad: "Finans",
    simge: "finans",
    ogeler: [
      { ad: "Ödemeler", simge: "odeme", yol: "/odemeler" },
      { ad: "Paketler", simge: "paket", yol: "/paketler" },
      { ad: "Gelir raporu", simge: "gelir", yol: "/gelir-raporu" },
    ],
  },
  {
    anahtar: "sistem",
    ad: "Sistem",
    simge: "sistem",
    ogeler: [
      { ad: "Bildirimler", simge: "bildirim", yol: "/bildirimler" },
      { ad: "Denetim kaydı", simge: "denetim", yol: "/denetim-kaydi" },
      { ad: "Ayarlar", simge: "sistem", yol: "/ayarlar" },
    ],
  },
];

/** Mobilde altta sabit duran hızlı sekmeler (son sekme "Menü" çekmeceyi açar). */
export const YONETICI_SEKMELERI: MenuOgesi[] = [
  { ad: "Genel bakış", simge: "genel", yol: "/genel-bakis" },
  TAKVIM,
  { ad: "Öğrenciler", simge: "kayit", yol: "/ogrenciler" },
  { ad: "Gruplar", simge: "grup", yol: "/gruplar" },
];

export const ANTRENOR_MENUSU: MenuBolumu[] = [
  { anahtar: "genel", ad: "Genel", simge: "genel", ogeler: [TAKVIM] },
];

export function ogeAktifMi(o: MenuOgesi, yol: string): boolean {
  if (!o.yol) return false;
  return [o.yol, ...(o.ekYollar ?? [])].some((p) => yol === p || yol.startsWith(`${p}/`));
}

export function aktifBolum(menu: MenuBolumu[], yol: string): MenuBolumu | undefined {
  return menu.find((b) => b.ogeler.some((o) => ogeAktifMi(o, yol)));
}

export function aktifOge(menu: MenuBolumu[], yol: string): MenuOgesi | undefined {
  for (const b of menu) for (const o of b.ogeler) if (ogeAktifMi(o, yol)) return o;
  return undefined;
}

export const VELI_MENUSU: MenuBolumu[] = [
  {
    anahtar: "panel",
    ad: "Panelim",
    simge: "genel",
    ogeler: [
      { ad: "Ana sayfa", simge: "genel", yol: "/panel" },
      { ad: "Profil", simge: "kayit", yol: "/profil" },
    ],
  },
];
