import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { resitUyarilariniGetir, type ResitUyarisi } from "../api/ogrenci";
import ResitGecisi from "../components/ResitGecisi";
import { hataMesaji } from "../lib/dogrulama";

const ROL_ADI: Record<string, string> = { anne: "Anne", baba: "Baba", diger: "Diğer", kendisi: "Kendisi" };

function ResitKarti() {
  const [liste, setListe] = useState<ResitUyarisi[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [secili, setSecili] = useState<ResitUyarisi | null>(null);
  const [bilgi, setBilgi] = useState<string | null>(null);

  const yukle = useCallback(async () => {
    try {
      setListe(await resitUyarilariniGetir());
      setHata(null);
    } catch (e) {
      setHata(hataMesaji(e));
    }
  }, []);

  useEffect(() => {
    void yukle();
  }, [yukle]);

  return (
    <section className="bg-yuzey border border-cizgi rounded-2xl p-4 sm:p-6">
      <h2 className="font-semibold mb-3">Reşit olan öğrenciler</h2>
      {bilgi && <p role="status" className="mb-3 rounded-lg border border-altin/60 bg-altin/10 text-altin-acik text-sm px-3 py-2">{bilgi}</p>}
      {hata && <p role="alert" className="text-sm text-hata">{hata}</p>}
      {!hata && liste === null && <p className="text-sm text-metin-soluk">Yükleniyor…</p>}
      {liste && liste.length === 0 && <p className="text-sm text-metin-soluk">Bekleyen reşit geçişi yok</p>}
      {liste && liste.length > 0 && (
        <ul className="space-y-2">
          {liste.map((o) => (
            <li key={o.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-cizgi px-3 py-2 text-sm">
              <div className="min-w-0">
                <Link to={`/ogrenciler/${o.id}`} className="font-medium hover:text-altin">{o.ad} {o.soyad}</Link>
                <div className="text-xs text-metin-soluk">
                  {o.yas} yaş • Birincil: {o.birincil_rol ? (ROL_ADI[o.birincil_rol] ?? o.birincil_rol) : "—"} • Veli hesabı: {o.veli_hesabi_var ? "var" : "yok"}
                </div>
              </div>
              <button
                className="rounded-lg border border-cizgi px-3 py-1.5 text-sm hover:border-altin"
                onClick={() => { setBilgi(null); setSecili(o); }}
              >
                Geçiş yap
              </button>
            </li>
          ))}
        </ul>
      )}
      {secili && (
        <ResitGecisi
          ogrenci={secili}
          onKapat={() => setSecili(null)}
          onTamam={() => {
            setBilgi(`${secili.ad} ${secili.soyad} için reşit geçişi yapıldı. Şimdi öğrenciye kendi panel hesabını açabilirsiniz.`);
            setSecili(null);
            void yukle();
          }}
        />
      )}
    </section>
  );
}

export default function GenelBakis() {
  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Genel bakış</h1>
      <div className="grid gap-4 md:grid-cols-2">
        <ResitKarti />
      </div>
    </div>
  );
}
