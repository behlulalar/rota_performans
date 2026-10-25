import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  fotoYukle,
  iletisimGuncelle,
  ogrenciGetir,
  ogrenciGuncelle,
  ogrenciOlustur,
  type Cinsiyet,
  type IletisimRol,
  type KimlikTur,
} from "../api/ogrenci";
import { ApiHata } from "../lib/api";
import { hataMesaji, ROL_ETIKET, tcGecerli, yasHesapla } from "../lib/dogrulama";
import { fotoKucult } from "../lib/fotoKucult";
import Kart from "../components/Kart";
import TelefonGirdisi from "../components/TelefonGirdisi";
import { apiyeCevir, bicimle, gecerliMi, rakamlaraCevir, TELEFON_HATA } from "../lib/telefon";
import SayfaBasligi from "../components/SayfaBasligi";
import { birincilDugme, dugme, girdi, tehlikeKutusu } from "../lib/stil";

type Kisi = { anahtar: number; rol: IletisimRol; ad_soyad: string; telefon: string; birincil: boolean };
type Hatalar = Record<string, string>;

let sayac = 0;
const yeniKisi = (rol: IletisimRol, birincil = false): Kisi => ({ anahtar: ++sayac, rol, ad_soyad: "", telefon: "", birincil });


function Alan({ etiket, hata, children }: { etiket: string; hata?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="text-[13px] text-metin-soluk">{etiket}</span>
      {children}
      {hata && <span className="block mt-1 text-[13px] text-hata">{hata}</span>}
    </label>
  );
}

export default function OgrenciForm() {
  const { id } = useParams();
  const duzenleme = Boolean(id);
  const git = useNavigate();

  const [ad, setAd] = useState("");
  const [soyad, setSoyad] = useState("");
  const [anneAdi, setAnneAdi] = useState("");
  const [babaAdi, setBabaAdi] = useState("");
  const [dogum, setDogum] = useState("");
  const [telefon, setTelefon] = useState("");
  const [cinsiyet, setCinsiyet] = useState<Cinsiyet | "">("");
  const [kimlikTur, setKimlikTur] = useState<KimlikTur>("tc");
  const [kimlikNo, setKimlikNo] = useState("");
  const [kisiler, setKisiler] = useState<Kisi[]>(() => [yeniKisi("anne", true), yeniKisi("baba"), yeniKisi("diger")]);
  const [rizalar, setRizalar] = useState({ aydinlatma: false, foto: false, whatsapp: false });
  const [foto, setFoto] = useState<Blob | null>(null);
  const [onizleme, setOnizleme] = useState<string | null>(null);
  const [hatalar, setHatalar] = useState<Hatalar>({});
  const [genelHata, setGenelHata] = useState<string | null>(null);
  const [yukleniyor, setYukleniyor] = useState(duzenleme);
  const [gonderiliyor, setGonderiliyor] = useState(false);

  useEffect(() => {
    if (!id) return;
    let iptal = false;
    ogrenciGetir(id)
      .then((o) => {
        if (iptal) return;
        setAd(o.ad);
        setSoyad(o.soyad);
        setAnneAdi(o.anne_adi ?? "");
        setBabaAdi(o.baba_adi ?? "");
        setDogum(o.dogum_tarihi);
        setCinsiyet(o.cinsiyet ?? "");
        setTelefon(rakamlaraCevir(o.telefon));
        setKimlikTur(o.kimlik_tur);
        setKisiler(o.iletisim_kisileri.map((k) => ({ anahtar: ++sayac, rol: k.rol, ad_soyad: k.ad_soyad, telefon: rakamlaraCevir(k.telefon), birincil: k.birincil })));
      })
      .catch((e) => !iptal && setGenelHata(hataMesaji(e)))
      .finally(() => !iptal && setYukleniyor(false));
    return () => {
      iptal = true;
    };
  }, [id]);

  useEffect(() => {
    if (!foto) return setOnizleme(null);
    const url = URL.createObjectURL(foto);
    setOnizleme(url);
    return () => URL.revokeObjectURL(url);
  }, [foto]);

  const yas = useMemo(() => yasHesapla(dogum), [dogum]);
  // Reşit öğrencide birincil iletişim sunucuda otomatik oluşur (yalnızca yeni kayıtta).
  const resit = !duzenleme && yas !== null && yas >= 18;
  const adSoyad = `${ad.trim()} ${soyad.trim()}`.trim();

  function kisiGuncelle(anahtar: number, yama: Partial<Kisi>) {
    setKisiler((l) => l.map((k) => (k.anahtar === anahtar ? { ...k, ...yama } : k)));
  }
  function birincilSec(anahtar: number) {
    setKisiler((l) => l.map((k) => ({ ...k, birincil: k.anahtar === anahtar })));
  }
  function kisiSil(anahtar: number) {
    setKisiler((l) => {
      const kalan = l.filter((k) => k.anahtar !== anahtar);
      if (kalan.length && !kalan.some((k) => k.birincil)) kalan[0] = { ...kalan[0], birincil: true };
      return kalan;
    });
  }

  async function fotoSec(dosya: File | undefined) {
    if (!dosya) return;
    try {
      setFoto(await fotoKucult(dosya));
      setHatalar((h) => ({ ...h, foto: "" }));
    } catch {
      setHatalar((h) => ({ ...h, foto: "Seçilen dosya işlenemedi. Lütfen bir görsel seçin." }));
    }
  }

  // Reşitte yalnızca dolu (kısmen dolu dahil) ek kişiler gönderilir; tamamen boş satırlar atlanır.
  const ekKisiler = kisiler.filter((k) => k.ad_soyad.trim() || k.telefon);

  function dogrula(): Hatalar {
    const h: Hatalar = {};
    if (!ad.trim()) h.ad = "Ad zorunludur.";
    if (!soyad.trim()) h.soyad = "Soyad zorunludur.";
    if (!dogum) h.dogum_tarihi = "Doğum tarihi zorunludur.";
    else if (yas === null || yas < 0) h.dogum_tarihi = "Geçerli bir doğum tarihi girin.";
    if (kimlikTur === "tc" && kimlikNo && !tcGecerli(kimlikNo)) h.kimlik_no = "Geçerli bir T.C. kimlik numarası girin (11 hane).";
    if (resit && !telefon) h.telefon = "Reşit öğrenci için telefon gerekli";
    else if (telefon && !gecerliMi(telefon)) h.telefon = TELEFON_HATA;
    if (resit) {
      if (ekKisiler.some((k) => !k.ad_soyad.trim() || !k.telefon)) h.kisiler = "Her iletişim kişisi için ad soyad ve telefon girin ya da satırı silin.";
      else if (ekKisiler.some((k) => !gecerliMi(k.telefon))) h.kisiler = TELEFON_HATA;
    } else if (kisiler.some((k) => !k.ad_soyad.trim() || !k.telefon)) h.kisiler = "Her iletişim kişisi için ad soyad ve telefon girin ya da satırı silin.";
    else if (kisiler.some((k) => !gecerliMi(k.telefon))) h.kisiler = TELEFON_HATA;
    else if (kisiler.filter((k) => k.birincil).length !== 1) h.kisiler = "Tam olarak bir birincil iletişim kişisi seçilmelidir.";
    else if (!kisiler.some((k) => k.rol === "diger" || k.rol === "kendisi")) h.kisiler = "En az bir Diğer veya Kendisi iletişim kişisi eklenmelidir.";
    if (!duzenleme && !rizalar.aydinlatma) h.aydinlatma = "KVKK aydınlatma metninin onaylanması gerekir.";
    return h;
  }

  async function gonder(e: FormEvent) {
    e.preventDefault();
    setGenelHata(null);
    const h = dogrula();
    setHatalar(h);
    if (Object.keys(h).length) return;

    const kisilerGovde = (resit ? ekKisiler : kisiler).map((k) => ({
      rol: k.rol,
      ad_soyad: k.ad_soyad.trim(),
      telefon: apiyeCevir(k.telefon) ?? "",
      birincil: resit ? false : k.birincil,
    }));
    const temel = {
      ad: ad.trim(),
      soyad: soyad.trim(),
      anne_adi: anneAdi.trim() || null,
      baba_adi: babaAdi.trim() || null,
      dogum_tarihi: dogum,
      cinsiyet: cinsiyet || null,
      telefon: apiyeCevir(telefon),
    };
    setGonderiliyor(true);
    try {
      if (duzenleme && id) {
        await ogrenciGuncelle(id, kimlikNo ? { ...temel, kimlik_tur: kimlikTur, kimlik_no: kimlikNo } : temel);
        await iletisimGuncelle(id, kisilerGovde);
        git(`/ogrenciler/${id}`);
        return;
      }
      const olusan = await ogrenciOlustur({
        ...temel,
        kimlik_tur: kimlikTur,
        kimlik_no: kimlikNo || null,
        iletisim_kisileri: kisilerGovde,
        rizalar,
      });
      let uyari: string | undefined;
      if (foto && rizalar.foto) {
        try {
          await fotoYukle(olusan.id, foto);
        } catch (err) {
          uyari = `Öğrenci kaydedildi ancak fotoğraf yüklenemedi: ${hataMesaji(err)}`;
        }
      }
      git(`/ogrenciler/${olusan.id}`, { state: { uyari } });
    } catch (err) {
      if (err instanceof ApiHata) {
        const alanlar: Hatalar = {};
        for (const a of err.alanlar) {
          const ilk = a.alan.split(".")[0];
          alanlar[ilk === "iletisim_kisileri" ? "kisiler" : ilk] = a.mesaj;
        }
        if (err.durum === 409) alanlar.kimlik_no = err.message;
        setHatalar(alanlar);
      }
      setGenelHata(hataMesaji(err));
    } finally {
      setGonderiliyor(false);
    }
  }

  if (yukleniyor) return <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>;

  return (
    <form onSubmit={gonder} noValidate className="space-y-4">
      <SayfaBasligi
        baslik={duzenleme ? "Öğrenciyi düzenle" : "Yeni öğrenci"}
        aciklama={duzenleme ? "Kayıt bilgilerini güncelleyin" : "Kişisel bilgiler, iletişim kişileri ve rızalar"}
        eylemler={<Link to={duzenleme ? `/ogrenciler/${id}` : "/ogrenciler"} className={dugme}>Vazgeç</Link>}
      />

      <Kart baslik="Kişisel bilgiler">
      <div className="grid sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4">
        <Alan etiket="Ad" hata={hatalar.ad}>
          <input className={girdi} value={ad} onChange={(e) => setAd(e.target.value)} autoComplete="off" />
        </Alan>
        <Alan etiket="Soyad" hata={hatalar.soyad}>
          <input className={girdi} value={soyad} onChange={(e) => setSoyad(e.target.value)} autoComplete="off" />
        </Alan>
        <Alan etiket="Anne adı" hata={hatalar.anne_adi}>
          <input className={girdi} value={anneAdi} onChange={(e) => setAnneAdi(e.target.value)} />
        </Alan>
        <Alan etiket="Baba adı" hata={hatalar.baba_adi}>
          <input className={girdi} value={babaAdi} onChange={(e) => setBabaAdi(e.target.value)} />
        </Alan>
        <Alan etiket="Doğum tarihi" hata={hatalar.dogum_tarihi}>
          <input type="date" className={girdi} value={dogum} max={new Date().toISOString().slice(0, 10)} onChange={(e) => setDogum(e.target.value)} />
        </Alan>
        <Alan etiket="Cinsiyet" hata={hatalar.cinsiyet}>
          <select className={girdi} value={cinsiyet} onChange={(e) => setCinsiyet(e.target.value as Cinsiyet | "")}>
            <option value="">Belirtilmedi</option>
            <option value="kadin">Kadın</option>
            <option value="erkek">Erkek</option>
          </select>
        </Alan>
        {yas !== null && yas >= 0 && yas < 5 && (
          <p className="col-span-full rounded-[3px] border border-uyari/40 bg-uyari-zemin text-uyari text-[13px] px-3 py-2">
            Dikkat: Öğrenci 5 yaşından küçük ({yas} yaş). Doğum tarihini kontrol edin; kayda devam edebilirsiniz.
          </p>
        )}
        <Alan etiket={resit ? "Telefon" : "Telefon (isteğe bağlı)"} hata={hatalar.telefon}>
          <TelefonGirdisi value={telefon} onChange={setTelefon} />
        </Alan>
        <Alan etiket="Kimlik türü">
          <select className={girdi} value={kimlikTur} onChange={(e) => setKimlikTur(e.target.value as KimlikTur)}>
            <option value="tc">T.C. Kimlik No</option>
            <option value="pasaport">Pasaport</option>
          </select>
        </Alan>
        <Alan etiket={kimlikTur === "tc" ? "T.C. kimlik numarası" : "Pasaport numarası"} hata={hatalar.kimlik_no}>
          <input
            className={girdi}
            value={kimlikNo}
            onChange={(e) => setKimlikNo(kimlikTur === "tc" ? e.target.value.replace(/\D/g, "").slice(0, 11) : e.target.value)}
            inputMode={kimlikTur === "tc" ? "numeric" : "text"}
            placeholder={duzenleme ? "Değiştirmek için yeni numarayı girin" : ""}
            autoComplete="off"
          />
        </Alan>
      </div>
      </Kart>

      <Kart baslik="İletişim kişileri">
        <p className="text-sm text-metin-soluk">Öğrenciyle ilgili tüm bildirimler yalnızca birincil iletişim kişisine gider.</p>
        {resit && (
          <div role="alert" className={`mt-3 ${tehlikeKutusu}`}>
            Reşit öğrenci — birincil iletişim kendisi: <span className="font-medium">{adSoyad || "Ad Soyad"}</span> ·{" "}
            {telefon ? <span className="num">{bicimle(apiyeCevir(telefon))}</span> : <span className="underline">telefon girin</span>}
            <p className="mt-1 text-xs font-normal">Aşağıya yalnızca ek kişileri (anne, baba, diğer) ekleyin; isteğe bağlıdır.</p>
          </div>
        )}
        <div className="mt-4 space-y-3">
          {kisiler.map((k) => (
            <div key={k.anahtar} className="rounded-[3px] border border-cizgi bg-yuzey-yuksek p-3 grid gap-3 sm:grid-cols-[8rem_1fr_1fr_auto] items-end">
              <label className="block">
                <span className="text-xs text-metin-soluk">Rol</span>
                <select className={girdi} value={k.rol} onChange={(e) => kisiGuncelle(k.anahtar, { rol: e.target.value as IletisimRol })}>
                  {(Object.keys(ROL_ETIKET) as IletisimRol[]).map((r) => (
                    <option key={r} value={r}>{ROL_ETIKET[r]}</option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-xs text-metin-soluk">Ad soyad</span>
                <input className={girdi} value={k.ad_soyad} onChange={(e) => kisiGuncelle(k.anahtar, { ad_soyad: e.target.value })} />
              </label>
              <label className="block">
                <span className="text-xs text-metin-soluk">Telefon</span>
                <TelefonGirdisi value={k.telefon} onChange={(t) => kisiGuncelle(k.anahtar, { telefon: t })} />
              </label>
              <div className="flex items-center justify-between gap-3 sm:justify-end">
                {!resit && (
                  <label className="flex items-center gap-2 text-sm min-h-11 md:min-h-0">
                    <input type="radio" name="birincil" checked={k.birincil} onChange={() => birincilSec(k.anahtar)} className="accent-altin size-4" />
                    Birincil iletişim
                  </label>
                )}
                <button type="button" onClick={() => kisiSil(k.anahtar)} className={`${dugme} text-metin-soluk hover:border-hata hover:text-hata`}>
                  Sil
                </button>
              </div>
            </div>
          ))}
        </div>
        {hatalar.kisiler && <p className="mt-2 text-sm text-hata">{hatalar.kisiler}</p>}
        <button type="button" onClick={() => setKisiler((l) => [...l, yeniKisi("diger", l.length === 0)])} className={`${dugme} mt-3`}>
          Kişi ekle
        </button>
      </Kart>

      {!duzenleme && (
        <Kart baslik="Rızalar">
          <div className="space-y-3">
          {([
            ["aydinlatma", "KVKK aydınlatma metnini okudum, onaylıyorum (zorunlu)"],
            ["foto", "Fotoğraf çekimi ve kullanımına izin veriyorum"],
            ["whatsapp", "WhatsApp ile bilgilendirme yapılmasına izin veriyorum"],
          ] as const).map(([anahtar, metin]) => (
            <label key={anahtar} className="flex items-start gap-3 text-sm">
              <input
                type="checkbox"
                checked={rizalar[anahtar]}
                onChange={(e) => {
                  setRizalar((r) => ({ ...r, [anahtar]: e.target.checked }));
                  if (anahtar === "foto" && !e.target.checked) setFoto(null);
                }}
                className="accent-altin size-4 mt-0.5"
              />
              <span>{metin}</span>
            </label>
          ))}
          {hatalar.aydinlatma && <p className="text-[13px] text-hata">{hatalar.aydinlatma}</p>}
          </div>
        </Kart>
      )}

      {!duzenleme ? (
        <Kart baslik="Fotoğraf">
          {!rizalar.foto ? (
            <p className="text-sm text-metin-soluk">Fotoğraf eklemek için yukarıda fotoğraf rızasının işaretlenmesi gerekir.</p>
          ) : (
            <div className="mt-3 flex items-center gap-4">
              <div className="size-20 rounded-[3px] overflow-hidden bg-yuzey-yuksek border border-cizgi shrink-0">
                {onizleme && <img src={onizleme} alt="Seçilen fotoğraf önizlemesi" className="size-full object-cover" />}
              </div>
              <div>
                <input type="file" accept="image/*" onChange={(e) => void fotoSec(e.target.files?.[0])} className="text-sm text-metin-soluk file:mr-3 file:rounded-[3px] file:border file:border-cizgi file:bg-yuzey-yuksek file:px-3 file:py-1.5 file:text-metin" />
                {foto && (
                  <button type="button" onClick={() => setFoto(null)} className="mt-2 block text-sm text-metin-soluk hover:text-hata">Fotoğrafı kaldır</button>
                )}
                {hatalar.foto && <p className="mt-1 text-sm text-hata">{hatalar.foto}</p>}
              </div>
            </div>
          )}
        </Kart>
      ) : (
        <p className="text-sm text-metin-soluk">Fotoğrafı değiştirmek için öğrenci detay sayfasını kullanın.</p>
      )}

      {genelHata && <p role="alert" className="text-[13px] text-hata">{genelHata}</p>}

      <div className="flex gap-3">
        <button type="submit" disabled={gonderiliyor} className={birincilDugme}>
          {gonderiliyor ? "Kaydediliyor…" : "Kaydet"}
        </button>
        <Link to={duzenleme ? `/ogrenciler/${id}` : "/ogrenciler"} className={dugme}>
          Vazgeç
        </Link>
      </div>
    </form>
  );
}
