const YOLLAR = {
  genel: "M3 10.5 9 4l6 6.5V15H3z",
  kayit: "M9 8.5a2.75 2.75 0 1 0 0-5.5 2.75 2.75 0 0 0 0 5.5zM3.5 15.5c.6-2.8 2.8-4.3 5.5-4.3s4.9 1.5 5.5 4.3",
  finans: "M2.5 5h13v9h-13zM2.5 8h13M5 11.5h3",
  sistem:
    "M9 11.3a2.3 2.3 0 1 0 0-4.6 2.3 2.3 0 0 0 0 4.6zM9 2.5v2M9 13.5v2M2.5 9h2M13.5 9h2M4.4 4.4l1.4 1.4M12.2 12.2l1.4 1.4M4.4 13.6l1.4-1.4M12.2 5.8l1.4-1.4",
  takvim: "M3 5h12v10H3zM3 8h12M6.5 3v3M11.5 3v3",
  grup: "M3 4h5v5H3zM10 4h5v5h-5zM3 11h5v4H3zM10 11h5v4h-5z",
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
  denetim: "M4 2.5h10v13H4zM6.5 6h5M6.5 9h5M6.5 12h3",
  odeme: "M2.5 5h13v9h-13zM2.5 8h13M5 11.5h3",
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
