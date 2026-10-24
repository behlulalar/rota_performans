// Seçilen görseli en uzun kenarı 1024 px olacak şekilde JPEG'e (kalite 0.85) dönüştürür.
export async function fotoKucult(dosya: File): Promise<Blob> {
  const bitmap = await createImageBitmap(dosya);
  const oran = Math.min(1, 1024 / Math.max(bitmap.width, bitmap.height));
  const tuval = document.createElement("canvas");
  tuval.width = Math.round(bitmap.width * oran);
  tuval.height = Math.round(bitmap.height * oran);
  const baglam = tuval.getContext("2d");
  if (!baglam) throw new Error("Görsel işlenemedi.");
  baglam.fillStyle = "#fff";
  baglam.fillRect(0, 0, tuval.width, tuval.height);
  baglam.drawImage(bitmap, 0, 0, tuval.width, tuval.height);
  bitmap.close();
  return new Promise((coz, red) =>
    tuval.toBlob((b) => (b ? coz(b) : red(new Error("Görsel işlenemedi."))), "image/jpeg", 0.85),
  );
}
