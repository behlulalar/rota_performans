import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ogrencileriGetir, type Liste } from "../api/ogrenci";
import DurumRozeti from "../components/DurumRozeti";
import OgrenciFoto from "../components/OgrenciFoto";
import { hataMesaji, ROL_ETIKET } from "../lib/dogrulama";

const BOYUT = 25;

export default function OgrenciListe() {
  const git = useNavigate();
  const [arama, setArama] = useState("");
  const [q, setQ] = useState("");
  const [durum, setDurum] = useState("");
  const [sayfa, setSayfa] = useState(1);
  const [veri, setVeri] = useState<Liste | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      setQ(arama.trim());
      setSayfa(1);
    }, 300);
    return () => clearTimeout(t);
  }, [arama]);

  useEffect(() => {
    let iptal = false;
    setYukleniyor(true);
    setHata(null);
    ogrencileriGetir({ q, durum, sayfa, boyut: BOYUT })
      .then((v) => !iptal && setVeri(v))
      .catch((e) => !iptal && setHata(hataMesaji(e)))
      .finally(() => !iptal && setYukleniyor(false));
    return () => {
      iptal = true;
    };
  }, [q, durum, sayfa]);

  const sayfaSayisi = veri ? Math.max(1, Math.ceil(veri.toplam / veri.boyut)) : 1;
  const kayitlar = veri?.kayitlar ?? [];

  return (
    <div>
      <div className="flex items-center justify-between gap-3 mb-4">
        <h1 className="text-xl font-semibold">Öğrenciler</h1>
        <Link to="/ogrenciler/yeni" className="rounded-lg bg-altin text-zemin font-semibold px-4 py-2 text-sm hover:bg-altin-acik">
          Yeni öğrenci
        </Link>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <input
          type="search"
          value={arama}
          onChange={(e) => setArama(e.target.value)}
          placeholder="Ad veya soyad ara…"
          className="flex-1 rounded-lg bg-yuzey border border-cizgi px-3 py-2.5 outline-none focus:border-altin"
        />
        <select
          value={durum}
          onChange={(e) => {
            setDurum(e.target.value);
            setSayfa(1);
          }}
          aria-label="Durum filtresi"
          className="rounded-lg bg-yuzey border border-cizgi px-3 py-2.5 outline-none focus:border-altin"
        >
          <option value="">Tüm durumlar</option>
          <option value="aktif">Aktif</option>
          <option value="pasif">Pasif</option>
        </select>
      </div>

      {hata && <p role="alert" className="text-sm text-hata mb-3">{hata}</p>}

      {yukleniyor && !veri ? (
        <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>
      ) : kayitlar.length === 0 && !yukleniyor && !hata ? (
        <div className="bg-yuzey border border-cizgi rounded-2xl p-10 text-center text-metin-soluk">
          {q || durum ? "Aramanıza uyan öğrenci bulunamadı." : "Henüz kayıtlı öğrenci yok."}
        </div>
      ) : (
        <div className={yukleniyor ? "opacity-60 transition-opacity" : ""}>
          {/* Masaüstü tablo */}
          <div className="hidden md:block bg-yuzey border border-cizgi rounded-2xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="text-left text-metin-soluk border-b border-cizgi">
                <tr>
                  <th className="p-3 w-14"></th>
                  <th className="p-3">Ad soyad</th>
                  <th className="p-3">Yaş</th>
                  <th className="p-3">Kimlik</th>
                  <th className="p-3">Birincil iletişim</th>
                  <th className="p-3">Durum</th>
                </tr>
              </thead>
              <tbody>
                {kayitlar.map((o) => (
                  <tr
                    key={o.id}
                    onClick={() => git(`/ogrenciler/${o.id}`)}
                    className="border-b border-cizgi last:border-0 hover:bg-yuzey-yuksek cursor-pointer"
                  >
                    <td className="p-3">
                      <OgrenciFoto id={o.id} fotoVar={o.foto_var} ad={o.ad} soyad={o.soyad} boyut="kucuk" />
                    </td>
                    <td className="p-3 font-medium">
                      <Link to={`/ogrenciler/${o.id}`} className="hover:text-altin">{o.ad} {o.soyad}</Link>
                    </td>
                    <td className="p-3">{o.yas}</td>
                    <td className="p-3 text-metin-soluk">{o.kimlik_maskeli ?? "—"}</td>
                    <td className="p-3">
                      {o.birincil_iletisim ? (
                        <>
                          <div>{o.birincil_iletisim.ad_soyad} <span className="text-metin-soluk">({ROL_ETIKET[o.birincil_iletisim.rol]})</span></div>
                          <div className="text-metin-soluk">{o.birincil_iletisim.telefon}</div>
                        </>
                      ) : "—"}
                    </td>
                    <td className="p-3"><DurumRozeti durum={o.durum} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobil kartlar */}
          <ul className="md:hidden space-y-3">
            {kayitlar.map((o) => (
              <li key={o.id}>
                <Link to={`/ogrenciler/${o.id}`} className="flex gap-3 bg-yuzey border border-cizgi rounded-2xl p-3">
                  <OgrenciFoto id={o.id} fotoVar={o.foto_var} ad={o.ad} soyad={o.soyad} boyut="kucuk" />
                  <div className="min-w-0 flex-1 text-sm">
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-medium">{o.ad} {o.soyad}</span>
                      <DurumRozeti durum={o.durum} />
                    </div>
                    <div className="text-metin-soluk">{o.yas} yaş · {o.kimlik_maskeli ?? "—"}</div>
                    {o.birincil_iletisim && (
                      <div className="mt-1 text-metin-soluk">
                        {o.birincil_iletisim.ad_soyad} · {o.birincil_iletisim.telefon}
                      </div>
                    )}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {veri && veri.toplam > 0 && (
        <div className="flex items-center justify-between mt-4 text-sm text-metin-soluk">
          <span>Toplam {veri.toplam} öğrenci</span>
          <div className="flex items-center gap-2">
            <button
              disabled={sayfa <= 1}
              onClick={() => setSayfa((s) => s - 1)}
              className="rounded-lg border border-cizgi px-3 py-1.5 disabled:opacity-40 hover:border-altin"
            >
              Önceki
            </button>
            <span>{sayfa} / {sayfaSayisi}</span>
            <button
              disabled={sayfa >= sayfaSayisi}
              onClick={() => setSayfa((s) => s + 1)}
              className="rounded-lg border border-cizgi px-3 py-1.5 disabled:opacity-40 hover:border-altin"
            >
              Sonraki
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
