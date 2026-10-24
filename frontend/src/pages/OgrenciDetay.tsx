import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { aktifEt, fotoSil, fotoYukle, hesapAc, hesapKaldir, hesapSifreSifirla, kimlikGetir, ogrenciGetir, pasifeAl, type OgrenciDetay as Detay, type RizaTur } from "../api/ogrenci";
import { gruplariGetir, ogrenciEkle, type GrupOzet } from "../api/grup";
import GeciciSifreKutusu from "../components/GeciciSifreKutusu";
import ResitGecisi from "../components/ResitGecisi";
import DurumRozeti from "../components/DurumRozeti";
import OgrenciFoto from "../components/OgrenciFoto";
import { hataMesaji, ROL_ETIKET, tarihBicimle } from "../lib/dogrulama";
import { fotoKucult } from "../lib/fotoKucult";

const RIZA_ADI: Record<RizaTur, string> = {
  aydinlatma: "KVKK aydınlatma",
  foto: "Fotoğraf",
  whatsapp: "WhatsApp bilgilendirme",
};

const dugme = "rounded-lg border border-cizgi px-3 py-1.5 text-sm hover:border-altin disabled:opacity-50";

export default function OgrenciDetay() {
  const { id } = useParams();
  const konum = useLocation();
  const git = useNavigate();
  const dosyaGirdisi = useRef<HTMLInputElement>(null);
  const [o, setO] = useState<Detay | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const bilgi = (konum.state as { uyari?: string } | null)?.uyari ?? null;
  const [kimlik, setKimlik] = useState<string | null>(null);
  const [surum, setSurum] = useState(0);
  const [mesgul, setMesgul] = useState(false);
  const [grupSecenekleri, setGrupSecenekleri] = useState<GrupOzet[] | null>(null);
  const [secilenGrup, setSecilenGrup] = useState("");
  const [hesapGiris, setHesapGiris] = useState("");
  const [sifre, setSifre] = useState<{ baslik: string; deger: string } | null>(null);
  const [hesapBilgi, setHesapBilgi] = useState<string | null>(null);
  const [resitAcik, setResitAcik] = useState(false);

  useEffect(() => {
    if (!id) return;
    let iptal = false;
    ogrenciGetir(id)
      .then((v) => !iptal && setO(v))
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => {
      iptal = true;
    };
  }, [id]);

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

  if (hata && !o) return <p role="alert" className="text-hata">{hata}</p>;
  if (!o || !id) return <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>;

  const fotoRizasi = o.rizalar.some((r) => r.tur === "foto" && r.verildi && !r.geri_cekildi);

  const durumDegistir = () =>
    islem(async () => {
      const aktif = o.durum === "aktif";
      if (!window.confirm(aktif ? "Öğrenci pasife alınsın mı?" : "Öğrenci tekrar aktif edilsin mi?")) return;
      setO(await (aktif ? pasifeAl(id) : aktifEt(id)));
    });

  const grupEkleAc = () =>
    islem(async () => {
      setGrupSecenekleri(await gruplariGetir(true));
    });

  const gruba = () =>
    islem(async () => {
      if (!secilenGrup) return;
      await ogrenciEkle(secilenGrup, id);
      setO(await ogrenciGetir(id));
      setSecilenGrup("");
      setGrupSecenekleri(null);
    });

  const kimlikGoster = () =>
    islem(async () => {
      if (!window.confirm("Tam kimlik numarası görüntülenecek. Bu işlem kayıt altına alınır. Devam edilsin mi?")) return;
      setKimlik((await kimlikGetir(id)).kimlik_no);
    });

  const birincil = o.iletisim_kisileri.find((k) => k.birincil) ?? null;
  const hesapEngeli = o.durum !== "aktif" ? "Öğrenci pasif olduğu için hesap açılamaz." : !birincil ? "Birincil iletişim kişisi olmadığı için hesap açılamaz." : null;
  const resitUyarisi = (u: string) => u.toLocaleLowerCase("tr").includes("reşit");

  const hesapAcIslem = () =>
    islem(async () => {
      setHesapBilgi(null);
      const y = await hesapAc(id, hesapGiris.trim() || undefined);
      setO(await ogrenciGetir(id));
      setHesapGiris("");
      if (y.gecici_sifre) setSifre({ baslik: `${y.giris} için geçici şifre`, deger: y.gecici_sifre });
      if (!y.yeni_hesap) setHesapBilgi("Bu giriş bilgisiyle mevcut bir veli hesabı vardı; öğrenci o hesaba bağlandı (kardeş). Yeni şifre oluşturulmadı.");
    });

  const hesapSifirla = () =>
    islem(async () => {
      if (!window.confirm("Hesap şifresi sıfırlansın mı? Eski şifre geçersiz olur.")) return;
      const y = await hesapSifreSifirla(id);
      setSifre({ baslik: `${o.hesap?.giris ?? "Hesap"} için yeni geçici şifre`, deger: y.gecici_sifre });
    });

  const hesapSil = () =>
    islem(async () => {
      if (!window.confirm("Hesap bu öğrenciden ayrılacak. Başka öğrenciye bağlı değilse giriş kapatılır. Devam edilsin mi?")) return;
      setHesapBilgi(null);
      setO(await hesapKaldir(id));
    });

  const fotoDegistir = (dosya: File | undefined) =>
    islem(async () => {
      if (!dosya) return;
      await fotoYukle(id, await fotoKucult(dosya));
      setO(await ogrenciGetir(id));
      setSurum((s) => s + 1);
    });

  const fotoKaldir = () =>
    islem(async () => {
      if (!window.confirm("Fotoğraf silinsin mi?")) return;
      await fotoSil(id);
      setO(await ogrenciGetir(id));
      setSurum((s) => s + 1);
    });

  return (
    <div className="max-w-3xl space-y-5">
      <div className="flex items-center justify-between gap-3">
        <Link to="/ogrenciler" className="text-sm text-metin-soluk hover:text-metin">← Öğrenciler</Link>
        <div className="flex gap-2">
          <button className={dugme} onClick={() => git(`/ogrenciler/${id}/duzenle`)}>Düzenle</button>
          <button className={dugme} disabled={mesgul} onClick={() => void durumDegistir()}>
            {o.durum === "aktif" ? "Pasife al" : "Aktif et"}
          </button>
        </div>
      </div>

      {bilgi && <p role="status" className="rounded-lg border border-altin/60 bg-altin/10 text-altin-acik text-sm px-3 py-2">{bilgi}</p>}
      {hata && <p role="alert" className="text-sm text-hata">{hata}</p>}

      {o.uyarilar.length > 0 && (
        <div className="rounded-xl border border-altin/60 bg-altin/10 px-4 py-3 text-sm text-altin-acik space-y-1">
          {o.uyarilar.map((u) => (
            <div key={u} className="flex flex-wrap items-center justify-between gap-2">
              <p>{u}</p>
              {resitUyarisi(u) && (
                <button className={dugme} onClick={() => { setHesapBilgi(null); setResitAcik(true); }}>Reşit geçişi yap</button>
              )}
            </div>
          ))}
        </div>
      )}

      <section className="bg-yuzey border border-cizgi rounded-2xl p-4 sm:p-6 flex flex-col sm:flex-row gap-5">
        <div className="shrink-0">
          <OgrenciFoto id={o.id} fotoVar={o.foto_var} ad={o.ad} soyad={o.soyad} boyut="buyuk" sinif="size-36 rounded-2xl text-3xl" surum={surum} />
          <input ref={dosyaGirdisi} type="file" accept="image/*" hidden onChange={(e) => { void fotoDegistir(e.target.files?.[0]); e.target.value = ""; }} />
          <div className="mt-3 flex gap-2 text-xs">
            <button className={dugme} disabled={mesgul || !fotoRizasi} onClick={() => dosyaGirdisi.current?.click()}>
              {o.foto_var ? "Değiştir" : "Fotoğraf ekle"}
            </button>
            {o.foto_var && <button className={dugme} disabled={mesgul} onClick={() => void fotoKaldir()}>Sil</button>}
          </div>
          {!fotoRizasi && <p className="mt-2 text-xs text-metin-soluk max-w-36">Fotoğraf rızası olmadığı için fotoğraf eklenemez.</p>}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-semibold">{o.ad} {o.soyad}</h1>
            <DurumRozeti durum={o.durum} />
          </div>
          <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
            <dt className="text-metin-soluk">Doğum tarihi</dt><dd>{tarihBicimle(o.dogum_tarihi)} ({o.yas} yaş)</dd>
            <dt className="text-metin-soluk">Cinsiyet</dt><dd>{o.cinsiyet === "kadin" ? "Kadın" : o.cinsiyet === "erkek" ? "Erkek" : "—"}</dd>
            <dt className="text-metin-soluk">Anne adı</dt><dd>{o.anne_adi || "—"}</dd>
            <dt className="text-metin-soluk">Baba adı</dt><dd>{o.baba_adi || "—"}</dd>
            <dt className="text-metin-soluk">{o.kimlik_tur === "tc" ? "T.C. kimlik no" : "Pasaport no"}</dt>
            <dd className="flex flex-wrap items-center gap-3">
              <span>{kimlik ?? o.kimlik_maskeli ?? "—"}</span>
              {o.kimlik_maskeli && !kimlik && (
                <button className={dugme} disabled={mesgul} onClick={() => void kimlikGoster()}>Tam numarayı göster</button>
              )}
            </dd>
            <dt className="text-metin-soluk">Kayıt tarihi</dt><dd>{tarihBicimle(o.kayit_tarihi)}</dd>
          </dl>
        </div>
      </section>

      <section className="bg-yuzey border border-cizgi rounded-2xl p-4 sm:p-6">
        <h2 className="font-semibold mb-3">Gruplar</h2>
        {(o.gruplar ?? []).length === 0 ? (
          <p className="text-sm text-metin-soluk">Öğrenci herhangi bir grupta değil.</p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {o.gruplar.map((g) => (
              <li key={g.id}>
                <Link to={`/gruplar/${g.id}`} className="inline-block rounded-full border border-cizgi px-3 py-1 text-sm hover:border-altin hover:text-altin">{g.ad}</Link>
              </li>
            ))}
          </ul>
        )}
        {o.durum === "aktif" && (
          <div className="mt-4">
            {grupSecenekleri === null ? (
              <button className={dugme} disabled={mesgul} onClick={() => void grupEkleAc()}>Gruba ekle</button>
            ) : (
              <div className="flex flex-col sm:flex-row gap-2">
                <select
                  value={secilenGrup}
                  onChange={(e) => setSecilenGrup(e.target.value)}
                  aria-label="Grup seç"
                  className="flex-1 rounded-lg bg-zemin border border-cizgi px-3 py-2 outline-none focus:border-altin"
                >
                  <option value="">Grup seçin…</option>
                  {grupSecenekleri.filter((g) => !o.gruplar?.some((x) => x.id === g.id)).map((g) => (
                    <option key={g.id} value={g.id}>{g.ad} ({g.ogrenci_sayisi}/{g.kontenjan})</option>
                  ))}
                </select>
                <button className={dugme} disabled={mesgul || !secilenGrup} onClick={() => void gruba()}>Ekle</button>
                <button className={dugme} onClick={() => { setGrupSecenekleri(null); setSecilenGrup(""); }}>Vazgeç</button>
              </div>
            )}
          </div>
        )}
      </section>

      <section className="bg-yuzey border border-cizgi rounded-2xl p-4 sm:p-6">
        <h2 className="font-semibold mb-3">İletişim kişileri</h2>
        {o.iletisim_kisileri.length === 0 ? (
          <p className="text-sm text-metin-soluk">İletişim kişisi yok.</p>
        ) : (
          <ul className="space-y-2">
            {o.iletisim_kisileri.map((k) => (
              <li key={k.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-cizgi px-3 py-2 text-sm">
                <div>
                  <div className="font-medium">{k.ad_soyad} <span className="text-metin-soluk font-normal">({ROL_ETIKET[k.rol]})</span></div>
                  <a href={`tel:${k.telefon}`} className="text-metin-soluk hover:text-altin">{k.telefon}</a>
                </div>
                <div className="flex gap-2 text-xs">
                  {k.birincil && <span className="rounded-full bg-altin text-zemin font-semibold px-2.5 py-0.5">Birincil</span>}
                  {k.whatsapp_izni && <span className="rounded-full border border-basari/50 text-basari px-2.5 py-0.5">WhatsApp izni</span>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="bg-yuzey border border-cizgi rounded-2xl p-4 sm:p-6">
        <h2 className="font-semibold mb-3">Panel hesabı</h2>
        {hesapBilgi && <p role="status" className="mb-3 rounded-lg border border-altin/60 bg-altin/10 text-altin-acik text-sm px-3 py-2">{hesapBilgi}</p>}
        {o.hesap === null ? (
          <div className="space-y-3 text-sm">
            <p className="text-metin-soluk">
              Panel hesabı yalnızca birincil iletişim kişisine açılır: {birincil ? birincil.ad_soyad : "—"}
            </p>
            <label className="block">
              <span className="text-metin-soluk">Giriş bilgisi (boş bırakılırsa birincil kişinin telefonu kullanılır)</span>
              <input
                className="mt-1 w-full rounded-lg bg-zemin border border-cizgi px-3 py-2 outline-none focus:border-altin disabled:opacity-50"
                value={hesapGiris}
                onChange={(e) => setHesapGiris(e.target.value)}
                placeholder={birincil?.telefon ?? ""}
                autoCapitalize="none"
                disabled={!!hesapEngeli}
              />
            </label>
            {hesapEngeli && <p className="text-hata">{hesapEngeli}</p>}
            <button className={dugme} disabled={mesgul || !!hesapEngeli} onClick={() => void hesapAcIslem()}>Hesap aç</button>
          </div>
        ) : (
          <div className="space-y-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{o.hesap.giris}</span>
              <span className="text-metin-soluk">({o.hesap.rol === "veli" ? "Veli" : "Öğrenci"})</span>
              <span className={`rounded-full border px-2.5 py-0.5 text-xs ${o.hesap.aktif ? "border-basari/50 text-basari" : "border-cizgi text-metin-soluk"}`}>
                {o.hesap.aktif ? "Aktif" : "Pasif"}
              </span>
            </div>
            {o.hesap.bagli_ogrenci_sayisi > 1 && (
              <p className="text-metin-soluk">Bu hesap {o.hesap.bagli_ogrenci_sayisi} öğrenciye bağlı (kardeşler).</p>
            )}
            <p className="text-metin-soluk">Hesap bu öğrenciden ayrılır. Başka öğrenciye bağlı değilse giriş kapatılır.</p>
            <div className="flex flex-wrap gap-2">
              <button className={dugme} disabled={mesgul} onClick={() => void hesapSifirla()}>Şifre sıfırla</button>
              <button className={dugme} disabled={mesgul} onClick={() => void hesapSil()}>Hesabı kaldır</button>
            </div>
          </div>
        )}
      </section>

      <section className="bg-yuzey border border-cizgi rounded-2xl p-4 sm:p-6">
        <h2 className="font-semibold mb-3">Rızalar</h2>
        <ul className="space-y-1.5 text-sm">
          {o.rizalar.map((r) => (
            <li key={r.tur} className="flex justify-between gap-3">
              <span>{RIZA_ADI[r.tur]}</span>
              <span className={r.verildi && !r.geri_cekildi ? "text-basari" : "text-metin-soluk"}>
                {r.geri_cekildi ? "Geri çekildi" : r.verildi ? "Verildi" : "Verilmedi"}
              </span>
            </li>
          ))}
        </ul>
      </section>
      {sifre && (
        <GeciciSifreKutusu
          sifre={sifre.deger}
          baslik={sifre.baslik}
          uyari="Bu şifre yalnızca şimdi görünür. Veliye/öğrenciye güvenli bir yoldan iletin."
          onKapat={() => setSifre(null)}
        />
      )}
      {resitAcik && (
        <ResitGecisi
          ogrenci={o}
          onKapat={() => setResitAcik(false)}
          onTamam={(d) => {
            setO(d);
            setResitAcik(false);
            setHesapBilgi("Reşit geçişi yapıldı. Şimdi öğrenciye kendi panel hesabını açabilirsiniz.");
          }}
        />
      )}
    </div>
  );
}
