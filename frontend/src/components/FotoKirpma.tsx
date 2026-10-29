import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type WheelEvent } from "react";
import Modal from "./Modal";
import { birincilDugme, dugme } from "../lib/stil";

const KUTU = 280; // kırpma karesinin kenarı (px)
const EN_COK_YAKIN = 4;
const CIKTI_EN_AZ = 256;
const CIKTI_EN_COK = 1024;

const sinirla = (n: number, alt: number, ust: number) => Math.min(ust, Math.max(alt, n));

/**
 * Fotoğrafı kare olarak kırpar: sürükleyerek kaydırma, yakınlaştırma (kaydırıcı, tekerlek, +/- düğmeleri, klavye oku).
 * Yuvarlak kılavuz, yuvarlak gösterilen yerlerde yüzün çerçevede kalmasına yardım eder. Çıktı kare JPEG'dir.
 */
/** Ekran pikselinin yerel piksele oranı (CSS zoom ile ölçeklenmiş kökte 1'den farklıdır). */
function ekranOlcegi(el: HTMLElement) {
  return el.offsetWidth > 0 ? el.getBoundingClientRect().width / el.offsetWidth : 1;
}

export default function FotoKirpma({
  kaynak,
  onKapat,
  onTamam,
}: {
  kaynak: Blob;
  onKapat: () => void;
  onTamam: (kirpilmis: Blob) => Promise<void> | void;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [boyut, setBoyut] = useState<{ g: number; y: number } | null>(null);
  const [yakin, setYakin] = useState(1);
  const [ofset, setOfset] = useState({ x: 0, y: 0 });
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const resim = useRef<HTMLImageElement | null>(null);
  const surukle = useRef<{ x: number; y: number; ox: number; oy: number; olcek: number } | null>(null);

  useEffect(() => {
    const u = URL.createObjectURL(kaynak);
    setUrl(u);
    setBoyut(null);
    setYakin(1);
    setOfset({ x: 0, y: 0 });
    return () => URL.revokeObjectURL(u);
  }, [kaynak]);

  // 1x yakınlaştırmada kısa kenar kareyi tam doldurur ("cover").
  const taban = boyut ? KUTU / Math.min(boyut.g, boyut.y) : 1;
  const olcek = taban * yakin;

  function ofsetSinirla(o: { x: number; y: number }, yeniOlcek = olcek) {
    if (!boyut) return o;
    const ex = Math.max(0, (boyut.g * yeniOlcek - KUTU) / 2);
    const ey = Math.max(0, (boyut.y * yeniOlcek - KUTU) / 2);
    return { x: sinirla(o.x, -ex, ex), y: sinirla(o.y, -ey, ey) };
  }

  function yakinlastir(deger: number) {
    const d = sinirla(deger, 1, EN_COK_YAKIN);
    setYakin(d);
    setOfset((o) => ofsetSinirla(o, taban * d));
  }

  function basla(e: PointerEvent<HTMLDivElement>) {
    e.currentTarget.setPointerCapture(e.pointerId);
    surukle.current = { x: e.clientX, y: e.clientY, ox: ofset.x, oy: ofset.y, olcek: ekranOlcegi(e.currentTarget) };
  }
  function tasi(e: PointerEvent<HTMLDivElement>) {
    const s = surukle.current;
    if (!s) return;
    // clientX ekran pikselidir; yazı boyutu (CSS zoom) yüzünden yerel piksele çevrilir.
    setOfset(ofsetSinirla({ x: s.ox + (e.clientX - s.x) / s.olcek, y: s.oy + (e.clientY - s.y) / s.olcek }));
  }
  function birak() {
    surukle.current = null;
  }
  function tekerlek(e: WheelEvent<HTMLDivElement>) {
    yakinlastir(yakin * (e.deltaY < 0 ? 1.08 : 1 / 1.08));
  }
  function tus(e: KeyboardEvent<HTMLDivElement>) {
    const adim = 12;
    const hareket: Record<string, [number, number]> = {
      ArrowLeft: [adim, 0],
      ArrowRight: [-adim, 0],
      ArrowUp: [0, adim],
      ArrowDown: [0, -adim],
    };
    if (hareket[e.key]) {
      e.preventDefault();
      setOfset((o) => ofsetSinirla({ x: o.x + hareket[e.key][0], y: o.y + hareket[e.key][1] }));
    } else if (e.key === "+" || e.key === "=") yakinlastir(yakin * 1.15);
    else if (e.key === "-") yakinlastir(yakin / 1.15);
  }

  async function kaydet() {
    const img = resim.current;
    if (!img || !boyut) return;
    setMesgul(true);
    setHata(null);
    try {
      // Kare çerçevenin görsel üzerindeki karşılığı (kaynak piksel).
      const kare = KUTU / olcek;
      const sx = (boyut.g * olcek - KUTU) / 2 / olcek - ofset.x / olcek;
      const sy = (boyut.y * olcek - KUTU) / 2 / olcek - ofset.y / olcek;
      const cikti = Math.round(sinirla(kare, CIKTI_EN_AZ, CIKTI_EN_COK));
      const tuval = document.createElement("canvas");
      tuval.width = cikti;
      tuval.height = cikti;
      const baglam = tuval.getContext("2d");
      if (!baglam) throw new Error("Görsel işlenemedi.");
      baglam.fillStyle = "#fff";
      baglam.fillRect(0, 0, cikti, cikti);
      baglam.drawImage(img, sx, sy, kare, kare, 0, 0, cikti, cikti);
      const blob = await new Promise<Blob>((coz, red) =>
        tuval.toBlob((b) => (b ? coz(b) : red(new Error("Görsel işlenemedi."))), "image/jpeg", 0.88),
      );
      await onTamam(blob);
    } catch (err) {
      setHata(err instanceof Error ? err.message : "Fotoğraf kaydedilemedi.");
      setMesgul(false);
    }
  }

  return (
    <Modal baslik="Fotoğrafı ayarla" onKapat={onKapat}>
      <div className="space-y-3">
        <p className="text-sm text-metin-soluk">
          Yüzün yuvarlak çerçevenin içinde kalmasını sağlayın: sürükleyerek kaydırın, kaydırıcıyla yakınlaştırın.
        </p>
        <div className="flex justify-center">
          <div
            role="group"
            tabIndex={0}
            aria-label="Fotoğraf kırpma alanı: oklarla kaydırın, artı ve eksi tuşlarıyla yakınlaştırın"
            onPointerDown={basla}
            onPointerMove={tasi}
            onPointerUp={birak}
            onPointerCancel={birak}
            onWheel={tekerlek}
            onKeyDown={tus}
            style={{ width: KUTU, height: KUTU, touchAction: "none" }}
            className="relative overflow-hidden rounded-[10px] bg-yuzey-yuksek border border-cizgi-guclu cursor-grab active:cursor-grabbing select-none"
          >
            {url && (
              <img
                ref={resim}
                src={url}
                alt=""
                draggable={false}
                onLoad={(e) => setBoyut({ g: e.currentTarget.naturalWidth, y: e.currentTarget.naturalHeight })}
                style={{
                  position: "absolute",
                  left: "50%",
                  top: "50%",
                  width: boyut ? boyut.g * olcek : undefined,
                  height: boyut ? boyut.y * olcek : undefined,
                  maxWidth: "none",
                  transform: `translate(calc(-50% + ${ofset.x}px), calc(-50% + ${ofset.y}px))`,
                  visibility: boyut ? "visible" : "hidden",
                }}
              />
            )}
            {/* Yuvarlak kılavuz: dışı karartılır */}
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-0"
              style={{ background: "radial-gradient(circle closest-side, transparent 98%, rgba(0,0,0,0.5) 100%)" }}
            />
            <div aria-hidden="true" className="pointer-events-none absolute inset-0 rounded-full border border-white/70" />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button type="button" className={`${dugme} !px-3`} aria-label="Uzaklaştır" onClick={() => yakinlastir(yakin / 1.15)}>−</button>
          <input
            type="range"
            aria-label="Yakınlaştırma"
            min={1}
            max={EN_COK_YAKIN}
            step={0.01}
            value={yakin}
            onChange={(e) => yakinlastir(Number(e.target.value))}
            className="flex-1 accent-altin min-h-11"
          />
          <button type="button" className={`${dugme} !px-3`} aria-label="Yakınlaştır" onClick={() => yakinlastir(yakin * 1.15)}>+</button>
        </div>

        {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
        <div className="flex flex-wrap justify-between gap-2">
          <button type="button" className={dugme} onClick={() => { setYakin(1); setOfset({ x: 0, y: 0 }); }}>Sıfırla</button>
          <div className="flex gap-2">
            <button type="button" className={dugme} onClick={onKapat}>Vazgeç</button>
            <button type="button" className={birincilDugme} disabled={!boyut || mesgul} onClick={() => void kaydet()}>
              {mesgul ? "Kaydediliyor…" : "Kaydet"}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
