const YOLLAR = {
  bugun: "M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11zM9 6v3.2l2.2 1.3",
  genel: "M3 10.5 9 4l6 6.5V15H3z",
  kayit: "M9 8.5a2.75 2.75 0 1 0 0-5.5 2.75 2.75 0 0 0 0 5.5zM3.5 15.5c.6-2.8 2.8-4.3 5.5-4.3s4.9 1.5 5.5 4.3",
  finans: "M2.5 5h13v9h-13zM2.5 8h13M5 11.5h3",
  sistem: "M13.97 7.46L15.70 7.85L15.70 10.15L13.97 10.54L13.60 11.43L14.55 12.93L12.93 14.55L11.43 13.60L10.54 13.97L10.15 15.70L7.85 15.70L7.46 13.97L6.57 13.60L5.07 14.55L3.45 12.93L4.40 11.43L4.03 10.54L2.30 10.15L2.30 7.85L4.03 7.46L4.40 6.57L3.45 5.07L5.07 3.45L6.57 4.40L7.46 4.03L7.85 2.30L10.15 2.30L10.54 4.03L11.43 4.40L12.93 3.45L14.55 5.07L13.60 6.57zM9 11.2a2.2 2.2 0 1 0 0-4.4 2.2 2.2 0 0 0 0 4.4z",
  takvim: "M3 5h12v10H3zM3 8h12M6.5 3v3M11.5 3v3",
  grup: "M3 4h5v5H3zM10 4h5v5h-5zM3 11h5v4H3zM10 11h5v4h-5z",
  yonetici: "M9 2.5l5.5 2v4.3c0 3.3-2.3 5.6-5.5 6.7-3.2-1.1-5.5-3.4-5.5-6.7V4.5zM6.5 9l1.8 1.8L11.7 7.4",
  antrenor: "M9 3l1.8 3.7 4 .6-2.9 2.8.7 4-3.6-1.9-3.6 1.9.7-4L3.2 7.3l4-.6z",
  gelir: "M3 15V9M7.5 15V5M12 15v-4M3 15h12.5",
  paket: "M3 6l6-3 6 3v7l-6 3-6-3zM3 6l6 3 6-3M9 9v7",
  gunes:
    "M9 12.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM9 1.5v2M9 14.5v2M1.5 9h2M14.5 9h2M3.7 3.7l1.4 1.4M12.9 12.9l1.4 1.4M3.7 14.3l1.4-1.4M12.9 5.1l1.4-1.4",
  ay: "M14.5 11A6 6 0 0 1 7 3.5a6 6 0 1 0 7.5 7.5z",
  cikis: "M7 3H3.5v12H7M11 6l3 3-3 3M14 9H7",
  menu: "M3 5h12M3 9h12M3 13h12",
  kapat: "M4.5 4.5l9 9M13.5 4.5l-9 9",
  bildirim: "M4.5 13.5V8a4.5 4.5 0 0 1 9 0v5.5M3 13.5h12M7.5 15.5h3",
  duyuru: "M3 7.5v3h2.5L12 14V4L5.5 7.5zM14.5 7a3 3 0 0 1 0 4",
  denetim: "M4 2.5h10v13H4zM6.5 6h5M6.5 9h5M6.5 12h3",
  durum: "M2 9h3.2l2-5.5 3.2 11 2-5.5H16",
  odeme: "M2.5 5h13v9h-13zM2.5 8h13M5 11.5h3",
  telefon: "M4 2.5h2.5l1.2 3.2-1.6 1.1a8 8 0 0 0 4.1 4.1l1.1-1.6 3.2 1.2V13a1.5 1.5 0 0 1-1.6 1.5A11 11 0 0 1 2.5 4.1 1.5 1.5 0 0 1 4 2.5z",
  eposta: "M2.5 4.5h13v9h-13zM2.5 5l6.5 5 6.5-5",
  ileri: "M7 4.5 11.5 9 7 13.5",
  konum: "M9 16s5-4.6 5-8.5a5 5 0 0 0-10 0C4 11.4 9 16 9 16zM9 9.3a1.8 1.8 0 1 0 0-3.6 1.8 1.8 0 0 0 0 3.6z",
} as const;

export type SimgeAdi = keyof typeof YOLLAR;

export default function Simge({ ad, boyut = 18, sinif }: { ad: SimgeAdi; boyut?: number; sinif?: string }) {
  return (
    <svg
      width={boyut}
      height={boyut}
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={sinif}
    >
      <path d={YOLLAR[ad]} />
    </svg>
  );
}

/** Menü gizle/göster okları (14×14 viewBox). */
export function Ok({ yon, sinif }: { yon: "sol" | "sag"; sinif?: string }) {
  return (
    <svg
      width={14}
      height={14}
      viewBox="0 0 14 14"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={sinif}
    >
      <path d={yon === "sol" ? "M8.5 3.5 5 7l3.5 3.5" : "M5.5 3.5 9 7l-3.5 3.5"} />
    </svg>
  );
}
