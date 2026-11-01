import { useEffect, useRef, useState } from "react";
import { bicimle, telefonSec } from "../lib/telefon";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { aktifEt, fotoSil, fotoYukle, hesapAc, hesapKaldir, hesapSifreSifirla, kimlikGetir, ogrenciGetir, pasifeAl, type OgrenciDetay as Detay, type RizaTur } from "../api/ogrenci";
import { gruplariGetir, ogrenciEkle, type GrupOzet } from "../api/grup";
import GeciciSifreKutusu from "../components/GeciciSifreKutusu";
import DersHakki from "../components/DersHakki";
import DevamOzeti from "../components/DevamOzeti";
import { ogrenciDevamGetir, type DevamOzeti as DevamVeri } from "../api/devam";
import OgrenciPaketleri from "../components/OgrenciPaketleri";
import ResitGecisi from "../components/ResitGecisi";
import DurumRozeti from "../components/DurumRozeti";
import OgrenciFoto from "../components/OgrenciFoto";
import { hataMesaji, ROL_ETIKET, tarihBicimle } from "../lib/dogrulama";
import FotoKirpma from "../components/FotoKirpma";
import { apiBlob } from "../lib/api";
import Kart from "../components/Kart";
import SayfaBasligi from "../components/SayfaBasligi";
import { bilgiKutusu, dugme, girdi, rozetBasari, rozetBirincil, rozetNotr, secimKutusu, tehlikeKutusu, uyariKutusu } from "../lib/stil";
import WhatsAppDugmesi from "../components/WhatsAppDugmesi";
import { useOnay } from "../components/OnayPenceresi";
import { useAuth } from "../auth/AuthProvider";

const RIZA_ADI: Record<RizaTur, string> = {
  aydinlatma: "KVKK aydınlatma",
  foto: "Fotoğraf",
  whatsapp: "WhatsApp bilgilendirme",
};


export default function OgrenciDetay() {
  const onayla = useOnay();
  const { kullanici } = useAuth();
  const [devam, setDevam] = useState<DevamVeri | null>(null);
  const { id } = useParams();
  const konum = useLocation();
  const git = useNavigate();
  const dosyaGirdisi = useRef<HTMLInputElement>(null);
  const [o, setO] = useState<Detay | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const bilgi = (konum.state as { uyari?: string } | null)?.uyari ?? null;
  const [kimlik, setKimlik] = useState<string | null>(null);
  const [kirpilacak, setKirpilacak] = useState<Blob | null>(null);
  const [surum, setSurum] = useState(0);
  const [hakSurum, setHakSurum] = useState(0);
  const [mesgul, setMesgul] = useState(false);
  const [grupSecenekleri, setGrupSecenekleri] = useState<GrupOzet[] | null>(null);
  const [secilenGrup, setSecilenGrup] = useState("");
  const [hesapGiris, setHesapGiris] = useState("");
  const [sifre, setSifre] = useState<{ baslik: string; deger: string; giris?: string; telefon?: string | null } | null>(null);
  const [hesapBilgi, setHesapBilgi] = useState<string | null>(null);
  const [resitAcik, setResitAcik] = useState(false);

  useEffect(() => {
    if (!id) return;
    ogrenciDevamGetir(id).then(setDevam, () => {});
  }, [id, hakSurum]);

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

  if (hata && !o) return <p role="alert" className="text-[13px] text-hata">{hata}</p>;
  if (!o || !id) return <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>;

  const fotoRizasi = o.rizalar.some((r) => r.tur === "foto" && r.verildi && !r.geri_cekildi);

  const durumDegistir = () =>
    islem(async () => {
      const aktif = o.durum === "aktif";
      if (!(await onayla({ baslik: aktif ? "Pasife al" : "Aktif et", mesaj: aktif ? "Öğrenci pasife alınsın mı?" : "Öğrenci tekrar aktif edilsin mi?", onayYazisi: aktif ? "Pasife al" : "Aktif et" }))) return;
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
      if (!(await onayla({ baslik: "Kimlik numarası", mesaj: "Tam kimlik numarası görüntülenecek. Bu işlem kayıt altına alınır. Devam edilsin mi?", onayYazisi: "Göster" }))) return;
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
      if (y.gecici_sifre) setSifre({ baslik: `${y.giris} için geçici şifre`, deger: y.gecici_sifre, giris: y.giris, telefon: telefonSec(y.giris, o?.birincil_iletisim?.telefon) });
      if (!y.yeni_hesap) setHesapBilgi("Bu giriş bilgisiyle mevcut bir veli hesabı vardı; öğrenci o hesaba bağlandı (kardeş). Yeni şifre oluşturulmadı.");
    });

  const hesapSifirla = () =>
    islem(async () => {
      if (!(await onayla({ baslik: "Şifre sıfırla", mesaj: "Hesap şifresi sıfırlansın mı? Eski şifre geçersiz olur.", onayYazisi: "Sıfırla" }))) return;
      const y = await hesapSifreSifirla(id);
      setSifre({ baslik: `${o.hesap?.giris ?? "Hesap"} için yeni geçici şifre`, deger: y.gecici_sifre, giris: o.hesap?.giris, telefon: telefonSec(o.hesap?.giris, o?.birincil_iletisim?.telefon) });
    });

  const hesapSil = () =>
    islem(async () => {
      if (!(await onayla({ baslik: "Hesabı ayır", mesaj: "Hesap bu öğrenciden ayrılacak. Başka öğrenciye bağlı değilse giriş kapatılır. Devam edilsin mi?", onayYazisi: "Ayır", tehlikeli: true }))) return;
      setHesapBilgi(null);
      setO(await hesapKaldir(id));
    });

  const fotoSec = (dosya: File | undefined) => {
    if (!dosya) return;
    if (!dosya.type.startsWith("image/")) return setHata("Lütfen bir görsel dosyası seçin.");
    setHata(null);
    setKirpilacak(dosya);
  };

  // Kayıtlı fotoğrafı (yüklenirken kare kırpılmamış olabilir) yeniden konumlandırmak için büyük boyutu açar.
  const fotoAyarla = () =>
    islem(async () => {
      setKirpilacak(await apiBlob(`/api/ogrenciler/${id}/foto?boyut=buyuk&v=${surum}`));
    });

  const fotoKaydet = async (blob: Blob) => {
    await fotoYukle(id, blob);
    setO(await ogrenciGetir(id));
    setSurum((s) => s + 1);
    setKirpilacak(null);
  };

  const fotoKaldir = () =>
    islem(async () => {
      if (!(await onayla({ baslik: "Fotoğrafı sil", mesaj: "Fotoğraf silinsin mi?", onayYazisi: "Sil", tehlikeli: true }))) return;
      await fotoSil(id);
      setO(await ogrenciGetir(id));
      setSurum((s) => s + 1);
    });

  const satirSinif = "flex flex-wrap items-center justify-between gap-2 px-6 py-2 min-h-[52px] border-t border-cizgi first:border-t-0 text-sm";

  return (
    <div className="space-y-4">
      <div>
        <Link to="/ogrenciler" className="inline-flex items-center min-h-11 md:min-h-0 text-[13px] text-metin-soluk hover:text-metin">← Öğrenciler</Link>
      </div>
      <SayfaBasligi
        baslik={`${o.ad} ${o.soyad}`}
        aciklama={`${o.yas} yaş · Kayıt tarihi ${tarihBicimle(o.kayit_tarihi)}`}
        rozet={<DurumRozeti durum={o.durum} />}
        eylemler={
          <>
            <button className={dugme} onClick={() => git(`/ogrenciler/${id}/duzenle`)}>Düzenle</button>
            <button className={dugme} disabled={mesgul} onClick={() => void durumDegistir()}>
              {o.durum === "aktif" ? "Pasife al" : "Aktif et"}
            </button>
          </>
        }
      />

      {bilgi && <p role="status" className={bilgiKutusu}>{bilgi}</p>}
      {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}

      {o.uyarilar.length > 0 && (
        <div className="space-y-2">
          {o.uyarilar.map((u) => (
            <div
              key={u}
              role={resitUyarisi(u) ? "alert" : undefined}
              className={`${resitUyarisi(u) ? tehlikeKutusu : uyariKutusu} flex flex-wrap items-center justify-between gap-2`}
            >
              <p>{u}</p>
              {resitUyarisi(u) && (
                <button className={dugme} onClick={() => { setHesapBilgi(null); setResitAcik(true); }}>Reşit geçişi yap</button>
              )}
            </div>
          ))}
        </div>
      )}

      <Kart baslik="Kişisel bilgiler">
        <div className="flex flex-col sm:flex-row gap-5">
          <div className="shrink-0">
            <OgrenciFoto id={o.id} fotoVar={o.foto_var} ad={o.ad} soyad={o.soyad} boyut="buyuk" sinif="size-32 rounded-[10px] text-3xl" surum={surum} />
            <input ref={dosyaGirdisi} type="file" accept="image/*" hidden onChange={(e) => { fotoSec(e.target.files?.[0]); e.target.value = ""; }} />
            <div className="mt-6 flex flex-wrap gap-2">
              <button className={dugme} disabled={mesgul || !fotoRizasi} onClick={() => dosyaGirdisi.current?.click()}>
                {o.foto_var ? "Değiştir" : "Fotoğraf ekle"}
              </button>
              {o.foto_var && <button className={dugme} disabled={mesgul || !fotoRizasi} onClick={() => void fotoAyarla()}>Ayarla</button>}
              {o.foto_var && <button className={dugme} disabled={mesgul} onClick={() => void fotoKaldir()}>Sil</button>}
            </div>
            {!fotoRizasi && <p className="mt-2 text-xs text-metin-soluk max-w-36">Fotoğraf rızası olmadığı için fotoğraf eklenemez.</p>}
          </div>

          <dl className="flex-1 min-w-0 grid grid-cols-[auto_1fr] items-center gap-x-6 gap-y-2.5 text-sm content-start">
            <dt className="text-metin-soluk">Doğum tarihi</dt><dd className="num">{tarihBicimle(o.dogum_tarihi)} ({o.yas} yaş)</dd>
            <dt className="text-metin-soluk">Telefon</dt><dd className="num flex flex-wrap items-center gap-3">
              {o.telefon ? bicimle(o.telefon) : "—"}
              <WhatsAppDugmesi telefon={o.telefon} ad={`${o.ad} ${o.soyad}`} />
            </dd>
            <dt className="text-metin-soluk">Cinsiyet</dt><dd>{o.cinsiyet === "kadin" ? "Kadın" : o.cinsiyet === "erkek" ? "Erkek" : "—"}</dd>
            <dt className="text-metin-soluk">Anne adı</dt><dd>{o.anne_adi || "—"}</dd>
            <dt className="text-metin-soluk">Baba adı</dt><dd>{o.baba_adi || "—"}</dd>
            <dt className="text-metin-soluk">{o.kimlik_tur === "tc" ? "T.C. kimlik no" : "Pasaport no"}</dt>
            <dd className="flex flex-wrap items-center gap-3">
              <span className="num">{kimlik ?? o.kimlik_maskeli ?? "—"}</span>
              {o.kimlik_maskeli && !kimlik && kullanici?.rol !== "destek" && (
                <button className={`${dugme} !min-h-9 !px-3`} disabled={mesgul} onClick={() => void kimlikGoster()}>Tam numarayı göster</button>
              )}
            </dd>
            <dt className="text-metin-soluk">Kayıt tarihi</dt><dd className="num">{tarihBicimle(o.kayit_tarihi)}</dd>
          </dl>
        </div>
      </Kart>

      <Kart baslik="Devam özeti" aciklama="Yoklaması alınmış derslere göre">
        {devam ? <DevamOzeti d={devam} /> : <p className="text-sm text-metin-soluk">Yükleniyor…</p>}
      </Kart>

      <DersHakki key={hakSurum} ogrenci={o} onYenile={setO} />

      <OgrenciPaketleri
        ogrenciId={id}
        aktif={o.durum === "aktif"}
        onOdemeDegisti={() => { void ogrenciGetir(id).then((y) => { setO(y); setHakSurum((s) => s + 1); }).catch((e) => setHata(hataMesaji(e))); }}
      />

      <Kart baslik="Gruplar">
        {(o.gruplar ?? []).length === 0 ? (
          <p className="text-sm text-metin-soluk">Öğrenci herhangi bir grupta değil.</p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {o.gruplar.map((g) => (
              <li key={g.id}>
                <Link to={`/gruplar/${g.id}`} className="inline-flex items-center min-h-11 rounded-[10px] border border-cizgi-guclu bg-yuzey-yuksek px-3 text-[13px] hover:border-altin hover:text-altin-metin">{g.ad}</Link>
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
                  className={`flex-1 ${secimKutusu}`}
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
      </Kart>

      <Kart baslik="İletişim kişileri" bosluksuz>
        {o.iletisim_kisileri.length === 0 ? (
          <p className="px-6 pb-6 text-sm text-metin-soluk">İletişim kişisi yok.</p>
        ) : (
          <ul className="border-t border-cizgi">
            {o.iletisim_kisileri.map((k) => (
              <li key={k.id} className={satirSinif}>
                <div>
                  <div className="font-medium">{k.ad_soyad} <span className="text-metin-soluk font-normal">({ROL_ETIKET[k.rol]})</span></div>
                  <a href={`tel:${k.telefon}`} className="num text-metin-soluk hover:text-altin-metin">{bicimle(k.telefon)}</a>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {k.birincil && <span className={rozetBirincil}>Birincil</span>}
                  {k.whatsapp_izni && <span className={rozetBasari}>WhatsApp izni</span>}
                  <WhatsAppDugmesi telefon={k.telefon} ad={k.ad_soyad} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </Kart>

      <Kart baslik="Panel hesabı">
        {hesapBilgi && <p role="status" className={`mb-3 ${bilgiKutusu}`}>{hesapBilgi}</p>}
        {o.hesap === null ? (
          <div className="space-y-3 text-sm">
            <p className="text-metin-soluk">
              Panel hesabı yalnızca birincil iletişim kişisine açılır: {birincil ? birincil.ad_soyad : "—"}
            </p>
            <label className="block">
              <span className="text-metin-soluk">Giriş bilgisi (boş bırakılırsa birincil kişinin telefonu kullanılır)</span>
              <input
                className={`${girdi} disabled:opacity-50`}
                value={hesapGiris}
                onChange={(e) => setHesapGiris(e.target.value)}
                placeholder={birincil ? bicimle(birincil.telefon) : ""}
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
              <span className="font-medium">{bicimle(o.hesap.giris)}</span>
              <span className="text-metin-soluk">({o.hesap.rol === "veli" ? "Veli" : "Öğrenci"})</span>
              <span className={o.hesap.aktif ? rozetBasari : rozetNotr}>
                {o.hesap.aktif ? "Aktif" : "Pasif"}
              </span>
            </div>
            {o.hesap.bagli_ogrenci_sayisi > 1 && (
              <p className="text-metin-soluk">Bu hesap {o.hesap.bagli_ogrenci_sayisi} öğrenciye bağlı (kardeşler).</p>
            )}
            <div className="flex flex-wrap gap-2">
              <button className={dugme} disabled={mesgul} onClick={() => void hesapSifirla()}>Şifre sıfırla</button>
              <button className={dugme} disabled={mesgul} onClick={() => void hesapSil()}>Hesabı kaldır</button>
            </div>
          </div>
        )}
      </Kart>

      <Kart baslik="Rızalar" bosluksuz>
        <ul className="border-t border-cizgi">
          {o.rizalar.map((r) => (
            <li key={r.tur} className={`${satirSinif} flex-nowrap`}>
              <span>{RIZA_ADI[r.tur]}</span>
              <span className={r.verildi && !r.geri_cekildi ? "text-basari" : "text-metin-soluk"}>
                {r.geri_cekildi ? "Geri çekildi" : r.verildi ? "Verildi" : "Verilmedi"}
              </span>
            </li>
          ))}
        </ul>
      </Kart>
      {sifre && (
        <GeciciSifreKutusu
          sifre={sifre.deger}
          baslik={sifre.baslik}
          giris={sifre.giris}
          telefon={sifre.telefon}
          uyari="Bu şifre yalnızca şimdi görünür. Veliye/öğrenciye güvenli bir yoldan iletin."
          onKapat={() => setSifre(null)}
        />
      )}
      {kirpilacak && <FotoKirpma kaynak={kirpilacak} onKapat={() => setKirpilacak(null)} onTamam={fotoKaydet} />}
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
