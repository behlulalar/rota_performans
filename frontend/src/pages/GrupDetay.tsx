import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { grupGetir, grupGuncelle, ogrenciCikar, ogrenciEkle, type GrupDetay as Detay } from "../api/grup";
import { ogrencileriGetir, type OgrenciOzet } from "../api/ogrenci";
import DolulukCubugu from "../components/DolulukCubugu";
import OgrenciFoto from "../components/OgrenciFoto";
import { hataMesaji, tarihBicimle } from "../lib/dogrulama";
import { GUNLER, saat } from "../lib/program";
import Kart from "../components/Kart";
import SayfaBasligi from "../components/SayfaBasligi";
import { dugme, girdi, rozetBasari, rozetNotr } from "../lib/stil";
import { useOnay } from "../components/OnayPenceresi";


export default function GrupDetay() {
  const onayla = useOnay();
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
      if (!(await onayla({ baslik: g.aktif ? "Pasife al" : "Aktif et", mesaj: g.aktif ? "Grup pasife alınsın mı?" : "Grup tekrar aktif edilsin mi?", onayYazisi: g.aktif ? "Pasife al" : "Aktif et" }))) return;
      setG(await grupGuncelle(id, { aktif: !g.aktif }));
    });

  const ekle = (o: OgrenciOzet) =>
    islem(async () => {
      setG(await ogrenciEkle(id, o.id));
      setArama("");
    });

  const cikar = (uyeId: string, ad: string) =>
    islem(async () => {
      if (!(await onayla({ baslik: "Gruptan çıkar", mesaj: `${ad} gruptan çıkarılsın mı?`, onayYazisi: "Çıkar", tehlikeli: true }))) return;
      setG(await ogrenciCikar(id, uyeId));
    });

  return (
    <div className="space-y-4">
      <div>
        <Link to="/gruplar" className="inline-flex items-center min-h-11 md:min-h-0 text-[13px] text-metin-soluk hover:text-metin">← Gruplar</Link>
      </div>
      <SayfaBasligi
        baslik={g.ad}
        aciklama={`${g.antrenor?.ad_soyad ?? "Antrenör atanmamış"} · ${g.ogrenci_sayisi}/${g.kontenjan} öğrenci`}
        rozet={<span className={g.aktif ? rozetBasari : rozetNotr}>{g.aktif ? "Aktif" : "Pasif"}</span>}
        eylemler={
          <>
            <button className={dugme} onClick={() => git(`/gruplar/${id}/duzenle`)}>Düzenle</button>
            <button className={dugme} disabled={mesgul} onClick={() => void durumDegistir()}>{g.aktif ? "Pasife al" : "Aktif et"}</button>
          </>
        }
      />

      {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}

      <Kart baslik="Grup bilgileri">
        <div className="space-y-4">
          <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
            <dt className="text-metin-soluk">Antrenör</dt><dd>{g.antrenor?.ad_soyad ?? "Atanmamış"}</dd>
            <dt className="text-metin-soluk">Program</dt>
            <dd>
              {g.program.length === 0 ? "Program yok" : (
                <ul className="num">
                  {[...g.program].sort((a, b) => a.gun - b.gun || a.baslangic.localeCompare(b.baslangic)).map((s, i) => (
                    <li key={s.id ?? i}>{GUNLER[s.gun - 1]} {saat(s.baslangic)}–{saat(s.bitis)}</li>
                  ))}
                </ul>
              )}
            </dd>
          </dl>
          <DolulukCubugu dolu={g.ogrenci_sayisi} kontenjan={g.kontenjan} />
        </div>
      </Kart>

      <Kart baslik={`Öğrenciler (${g.ogrenciler.length})`} bosluksuz>
        {g.ogrenciler.length === 0 ? (
          <p className="px-6 pb-6 text-sm text-metin-soluk">Gruba kayıtlı öğrenci yok.</p>
        ) : (
          <ul className="border-t border-cizgi">
            {g.ogrenciler.map((o) => (
              <li key={o.id} className="flex items-center gap-3 px-6 py-1.5 min-h-[52px] border-t border-cizgi first:border-t-0 text-sm">
                <OgrenciFoto id={o.id} fotoVar={o.foto_var} ad={o.ad} soyad={o.soyad} boyut="kucuk" sinif="size-8 rounded-full text-[11px]" />
                <div className="min-w-0 flex-1">
                  <Link to={`/ogrenciler/${o.id}`} className="font-medium hover:text-altin-metin">{o.ad} {o.soyad}</Link>
                  <div className="num text-xs text-metin-soluk">{o.yas} yaş · Katılım: {tarihBicimle(o.katilim_baslangic)}</div>
                </div>
                <button className={dugme} disabled={mesgul} onClick={() => void cikar(o.id, `${o.ad} ${o.soyad}`)}>Gruptan çıkar</button>
              </li>
            ))}
          </ul>
        )}
      </Kart>

      <Kart baslik="Öğrenci ekle" bosluksuz>
        <div className="px-6 pb-4">
          <input
            type="search"
            value={arama}
            onChange={(e) => setArama(e.target.value)}
            placeholder="Aktif öğrenci ara…"
            className={`${girdi} mt-0`}
          />
          {aramaYapildi && adaylar.length === 0 && <p className="mt-3 text-sm text-metin-soluk">Eklenebilecek öğrenci bulunamadı.</p>}
        </div>
        {adaylar.length > 0 && (
          <ul className="border-t border-cizgi">
            {adaylar.map((o) => (
              <li key={o.id} className="flex items-center gap-3 px-6 py-1.5 min-h-[52px] border-t border-cizgi first:border-t-0 text-sm">
                <OgrenciFoto id={o.id} fotoVar={o.foto_var} ad={o.ad} soyad={o.soyad} boyut="kucuk" sinif="size-8 rounded-full text-[11px]" />
                <div className="min-w-0 flex-1">
                  <div className="font-medium">{o.ad} {o.soyad}</div>
                  <div className="num text-xs text-metin-soluk">{o.yas} yaş</div>
                </div>
                <button className={dugme} disabled={mesgul} onClick={() => void ekle(o)}>Ekle</button>
              </li>
            ))}
          </ul>
        )}
      </Kart>
    </div>
  );
}
