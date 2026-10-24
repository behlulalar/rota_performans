import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { grupGetir, grupGuncelle, ogrenciCikar, ogrenciEkle, type GrupDetay as Detay } from "../api/grup";
import { ogrencileriGetir, type OgrenciOzet } from "../api/ogrenci";
import DolulukCubugu from "../components/DolulukCubugu";
import OgrenciFoto from "../components/OgrenciFoto";
import { hataMesaji, tarihBicimle } from "../lib/dogrulama";
import { GUNLER, saat } from "../lib/program";

const dugme = "rounded-lg border border-cizgi px-3 py-1.5 text-sm hover:border-altin disabled:opacity-50";

export default function GrupDetay() {
  const { id } = useParams();
  const git = useNavigate();
  const [g, setG] = useState<Detay | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const [arama, setArama] = useState("");
  const [sonuc, setSonuc] = useState<OgrenciOzet[]>([]);
  const [aramaYapildi, setAramaYapildi] = useState(false);

  useEffect(() => {
    if (!id) return;
    let iptal = false;
    grupGetir(id)
      .then((v) => !iptal && setG(v))
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => {
      iptal = true;
    };
  }, [id]);

  useEffect(() => {
    const q = arama.trim();
    if (!q) {
      setSonuc([]);
      setAramaYapildi(false);
      return;
    }
    let iptal = false;
    const t = setTimeout(() => {
      ogrencileriGetir({ q, durum: "aktif", sayfa: 1, boyut: 10 })
        .then((v) => {
          if (iptal) return;
          setSonuc(v.kayitlar);
          setAramaYapildi(true);
        })
        .catch((e) => !iptal && setHata(hataMesaji(e)));
    }, 300);
    return () => {
      iptal = true;
      clearTimeout(t);
    };
  }, [arama]);

  async function islem(is: () => Promise<void>) {
    setMesgul(true);
    setHata(null);
    try {
      await is();
    } catch (e) {
      setHata(hataMesaji(e));
    } finally {
      setMesgul(false);
    }
  }

  if (hata && !g) return <p role="alert" className="text-hata">{hata}</p>;
  if (!g || !id) return <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>;

  const uyeIdler = new Set(g.ogrenciler.map((o) => o.id));
  const adaylar = sonuc.filter((o) => !uyeIdler.has(o.id));

  const durumDegistir = () =>
    islem(async () => {
      if (!window.confirm(g.aktif ? "Grup pasife alınsın mı?" : "Grup tekrar aktif edilsin mi?")) return;
      setG(await grupGuncelle(id, { aktif: !g.aktif }));
    });

  const ekle = (o: OgrenciOzet) =>
    islem(async () => {
      setG(await ogrenciEkle(id, o.id));
      setArama("");
    });

  const cikar = (uyeId: string, ad: string) =>
    islem(async () => {
      if (!window.confirm(`${ad} gruptan çıkarılsın mı?`)) return;
      setG(await ogrenciCikar(id, uyeId));
    });

  return (
    <div className="max-w-3xl space-y-5">
      <div className="flex items-center justify-between gap-3">
        <Link to="/gruplar" className="text-sm text-metin-soluk hover:text-metin">← Gruplar</Link>
        <div className="flex gap-2">
          <button className={dugme} onClick={() => git(`/gruplar/${id}/duzenle`)}>Düzenle</button>
          <button className={dugme} disabled={mesgul} onClick={() => void durumDegistir()}>{g.aktif ? "Pasife al" : "Aktif et"}</button>
        </div>
      </div>

      {hata && <p role="alert" className="text-sm text-hata">{hata}</p>}

      <section className="bg-yuzey border border-cizgi rounded-2xl p-4 sm:p-6 space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold">{g.ad}</h1>
          <span className={`inline-block rounded-full border px-2.5 py-0.5 text-xs ${g.aktif ? "border-basari/50 text-basari" : "border-cizgi text-metin-soluk"}`}>
            {g.aktif ? "Aktif" : "Pasif"}
          </span>
        </div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          <dt className="text-metin-soluk">Antrenör</dt><dd>{g.antrenor?.ad_soyad ?? "Atanmamış"}</dd>
          <dt className="text-metin-soluk">Program</dt>
          <dd>
            {g.program.length === 0 ? "Program yok" : (
              <ul>
                {[...g.program].sort((a, b) => a.gun - b.gun || a.baslangic.localeCompare(b.baslangic)).map((s, i) => (
                  <li key={s.id ?? i}>{GUNLER[s.gun - 1]} {saat(s.baslangic)}–{saat(s.bitis)}</li>
                ))}
              </ul>
            )}
          </dd>
        </dl>
        <DolulukCubugu dolu={g.ogrenci_sayisi} kontenjan={g.kontenjan} />
      </section>

      <section className="bg-yuzey border border-cizgi rounded-2xl p-4 sm:p-6">
        <h2 className="font-semibold mb-3">Öğrenciler ({g.ogrenciler.length})</h2>
        {g.ogrenciler.length === 0 ? (
          <p className="text-sm text-metin-soluk">Gruba kayıtlı öğrenci yok.</p>
        ) : (
          <ul className="space-y-2">
            {g.ogrenciler.map((o) => (
              <li key={o.id} className="flex items-center gap-3 rounded-xl border border-cizgi px-3 py-2 text-sm">
                <OgrenciFoto id={o.id} fotoVar={o.foto_var} ad={o.ad} soyad={o.soyad} boyut="kucuk" />
                <div className="min-w-0 flex-1">
                  <Link to={`/ogrenciler/${o.id}`} className="font-medium hover:text-altin">{o.ad} {o.soyad}</Link>
                  <div className="text-metin-soluk">{o.yas} yaş · Katılım: {tarihBicimle(o.katilim_baslangic)}</div>
                </div>
                <button className={dugme} disabled={mesgul} onClick={() => void cikar(o.id, `${o.ad} ${o.soyad}`)}>Gruptan çıkar</button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="bg-yuzey border border-cizgi rounded-2xl p-4 sm:p-6">
        <h2 className="font-semibold mb-3">Öğrenci ekle</h2>
        <input
          type="search"
          value={arama}
          onChange={(e) => setArama(e.target.value)}
          placeholder="Aktif öğrenci ara…"
          className="w-full rounded-lg bg-zemin border border-cizgi px-3 py-2.5 outline-none focus:border-altin"
        />
        {aramaYapildi && adaylar.length === 0 && <p className="mt-3 text-sm text-metin-soluk">Eklenebilecek öğrenci bulunamadı.</p>}
        {adaylar.length > 0 && (
          <ul className="mt-3 space-y-2">
            {adaylar.map((o) => (
              <li key={o.id} className="flex items-center gap-3 rounded-xl border border-cizgi px-3 py-2 text-sm">
                <OgrenciFoto id={o.id} fotoVar={o.foto_var} ad={o.ad} soyad={o.soyad} boyut="kucuk" />
                <div className="min-w-0 flex-1">
                  <div className="font-medium">{o.ad} {o.soyad}</div>
                  <div className="text-metin-soluk">{o.yas} yaş</div>
                </div>
                <button className={dugme} disabled={mesgul} onClick={() => void ekle(o)}>Ekle</button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
