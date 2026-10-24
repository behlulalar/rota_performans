import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ogrencileriGetir, type Liste } from "../api/ogrenci";
import DurumRozeti from "../components/DurumRozeti";
import OgrenciFoto from "../components/OgrenciFoto";
import { hataMesaji, ROL_ETIKET } from "../lib/dogrulama";
import SayfaBasligi from "../components/SayfaBasligi";
import { birincilDugme, dugme, satir, secimKutusu, td, th } from "../lib/stil";

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
      <SayfaBasligi
        baslik="Öğrenciler"
        aciklama={veri ? `${veri.toplam} öğrenci listeleniyor` : "Kayıtlı öğrenciler, iletişim ve grup bilgileri"}
        eylemler={<Link to="/ogrenciler/yeni" className={birincilDugme}>Yeni öğrenci</Link>}
      />

      <div className="flex flex-col sm:flex-row gap-2 mb-4">
        <input
          type="search"
          value={arama}
          onChange={(e) => setArama(e.target.value)}
          placeholder="Ad veya soyad ara…"
          className={`flex-1 ${secimKutusu}`}
        />
        <select
          value={durum}
          onChange={(e) => {
            setDurum(e.target.value);
            setSayfa(1);
          }}
          aria-label="Durum filtresi"
          className={secimKutusu}
        >
          <option value="">Tüm durumlar</option>
          <option value="aktif">Aktif</option>
          <option value="pasif">Pasif</option>
        </select>
      </div>

      {hata && <p role="alert" className="text-[13px] text-hata mb-3">{hata}</p>}

      {yukleniyor && !veri ? (
        <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>
      ) : kayitlar.length === 0 && !yukleniyor && !hata ? (
        <div className="bg-yuzey border border-cizgi rounded-[5px] p-10 text-center text-metin-soluk">
          {q || durum ? "Aramanıza uyan öğrenci bulunamadı." : "Henüz kayıtlı öğrenci yok."}
        </div>
      ) : (
        <div className={yukleniyor ? "opacity-60 transition-opacity" : ""}>
          {/* Masaüstü tablo */}
          <div className="hidden md:block bg-yuzey border border-cizgi rounded-[5px] overflow-hidden">
            <table className="w-full text-[13px]">
              <thead>
                <tr>
                  <th className={`${th} w-14`}></th>
                  <th className={th}>Ad soyad</th>
                  <th className={th}>Yaş</th>
                  <th className={th}>Kimlik</th>
                  <th className={th}>Birincil iletişim</th>
                  <th className={th}>Durum</th>
                </tr>
              </thead>
              <tbody>
                {kayitlar.map((o) => (
                  <tr key={o.id} onClick={() => git(`/ogrenciler/${o.id}`)} className={`${satir} cursor-pointer`}>
                    <td className="px-4 h-[52px]">
                      <OgrenciFoto id={o.id} fotoVar={o.foto_var} ad={o.ad} soyad={o.soyad} boyut="kucuk" sinif="size-8 rounded-full text-[11px]" />
                    </td>
                    <td className={`${td} font-medium`}>
                      <Link to={`/ogrenciler/${o.id}`} className="hover:text-altin-metin">{o.ad} {o.soyad}</Link>
                    </td>
                    <td className={`${td} num`}>{o.yas}</td>
                    <td className={`${td} num text-metin-soluk`}>{o.kimlik_maskeli ?? "—"}</td>
                    <td className="px-4 py-1.5 h-[52px]">
                      {o.birincil_iletisim ? (
                        <div className="leading-4">
                          <div>{o.birincil_iletisim.ad_soyad} <span className="text-metin-soluk">({ROL_ETIKET[o.birincil_iletisim.rol]})</span></div>
                          <div className="num text-metin-soluk text-xs">{o.birincil_iletisim.telefon}</div>
                        </div>
                      ) : "—"}
                    </td>
                    <td className={td}><DurumRozeti durum={o.durum} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobil kartlar */}
          <ul className="md:hidden space-y-2">
            {kayitlar.map((o) => (
              <li key={o.id}>
                <Link to={`/ogrenciler/${o.id}`} className="flex gap-3 bg-yuzey border border-cizgi rounded-[5px] p-4 min-h-11">
                  <OgrenciFoto id={o.id} fotoVar={o.foto_var} ad={o.ad} soyad={o.soyad} boyut="kucuk" />
                  <div className="min-w-0 flex-1 text-[13px]">
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-medium">{o.ad} {o.soyad}</span>
                      <DurumRozeti durum={o.durum} />
                    </div>
                    <div className="num text-metin-soluk">{o.yas} yaş · {o.kimlik_maskeli ?? "—"}</div>
                    {o.birincil_iletisim && (
                      <div className="num mt-1 text-metin-soluk">
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
        <div className="flex items-center justify-between mt-3 text-[13px] text-metin-soluk">
          <span className="num">Toplam {veri.toplam} öğrenci</span>
          <div className="flex items-center gap-2">
            <button disabled={sayfa <= 1} onClick={() => setSayfa((s) => s - 1)} className={dugme}>
              Önceki
            </button>
            <span className="num">{sayfa} / {sayfaSayisi}</span>
            <button disabled={sayfa >= sayfaSayisi} onClick={() => setSayfa((s) => s + 1)} className={dugme}>
              Sonraki
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
