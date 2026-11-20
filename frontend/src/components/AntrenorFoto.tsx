import OgrenciFoto from "./OgrenciFoto";

/** Antrenör avatarı: fotoğraf yoksa baş harfler. Fotoğraf /api/antrenorler/{id}/foto ucundan (yetkiye göre) gelir. */
export default function AntrenorFoto({
  id,
  fotoVar,
  adSoyad,
  boyut = "kucuk",
  sinif = "size-8 rounded-full",
  surum = 0,
}: {
  id: string;
  fotoVar: boolean;
  adSoyad: string;
  boyut?: "kucuk" | "buyuk";
  sinif?: string;
  surum?: number;
}) {
  const parcalar = adSoyad.trim().split(/\s+/);
  const ad = parcalar[0] ?? "";
  const soyad = parcalar.length > 1 ? parcalar[parcalar.length - 1] : "";
  return <OgrenciFoto id={id} fotoVar={fotoVar} ad={ad} soyad={soyad} boyut={boyut} sinif={sinif} surum={surum} antrenor />;
}
