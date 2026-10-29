import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  yoneticiGuncelle,
  yoneticiOlustur,
  yoneticiSifreSifirla,
  yoneticileriGetir,
  type YoneticiOzet,
} from "../api/yonetici";
import GeciciSifreKutusu from "../components/GeciciSifreKutusu";
import { useOnay } from "../components/OnayPenceresi";
import SayfaBasligi from "../components/SayfaBasligi";
import { hataMesaji } from "../lib/dogrulama";
import { girisiBicimle } from "../lib/hatirla";
import { birincilDugme, dugme, girdi, rozetBasari, rozetNotr, satir, td, th } from "../lib/stil";

const KENDI_NOTU = "Kendi hesabınız için Ayarlar > Hesabım bölümünü kullanın";

function AktifRozeti({ aktif }: { aktif: boolean }) {
  return <span className={aktif ? rozetBasari : rozetNotr}>{aktif ? "Aktif" : "Pasif"}</span>;
}

function sonGiris(s: string | null): string {
  return s ? new Date(s).toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" }) : "Henüz girmedi";
}

const adi = (y: YoneticiOzet) => y.ad_soyad || y.giris;

export default function YoneticiListe() {
  const onayla = useOnay();
  const [liste, setListe] = useState<YoneticiOzet[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const [sifre, setSifre] = useState<{ baslik: string; deger: string; giris: string } | null>(null);
  const [yeniAcik, setYeniAcik] = useState(false);
  const [duzenlenen, setDuzenlenen] = useState<YoneticiOzet | null>(null);

  const yukle = useCallback(async () => {
    try {
      setListe(await yoneticileriGetir());
    } catch (e) {
      setHata(hataMesaji(e));
    }
  }, []);

  useEffect(() => {
    void yukle();
  }, [yukle]);

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

  const durumDegistir = (y: YoneticiOzet) =>
    islem(async () => {
      const onay = await onayla({
        baslik: y.aktif ? "Pasife al" : "Aktif et",
        mesaj: y.aktif
          ? `${adi(y)} pasife alınsın mı? Açık oturumları kapanır ve giriş yapamaz.`
          : `${adi(y)} tekrar aktif edilsin mi?`,
        onayYazisi: y.aktif ? "Pasife al" : "Aktif et",
      });
      if (!onay) return;
      await yoneticiGuncelle(y.id, { aktif: !y.aktif });
      await yukle();
    });

  const sifirla = (y: YoneticiOzet) =>
    islem(async () => {
      if (!(await onayla({ baslik: "Şifre sıfırla", mesaj: `${adi(y)} için şifre sıfırlansın mı? Eski şifre geçersiz olur, açık oturumları kapanır.`, onayYazisi: "Sıfırla" }))) return;
      const r = await yoneticiSifreSifirla(y.id);
      setSifre({ baslik: `${adi(y)} için yeni geçici şifre`, deger: r.gecici_sifre, giris: y.giris });
    });

  const eylemler = (y: YoneticiOzet) => (
    <>
      <button className={dugme} onClick={() => setDuzenlenen(y)}>Düzenle</button>
      <button className={dugme} disabled={mesgul || y.ben} title={y.ben ? KENDI_NOTU : undefined} onClick={() => void sifirla(y)}>Şifre sıfırla</button>
      <button className={dugme} disabled={mesgul || (y.ben && y.aktif)} title={y.ben ? "Kendi hesabınızı pasife alamazsınız" : undefined} onClick={() => void durumDegistir(y)}>{y.aktif ? "Pasife al" : "Aktif et"}</button>
    </>
  );

  const siz = (y: YoneticiOzet) => (y.ben ? <span className="text-metin-soluk font-normal"> (siz)</span> : null);

  return (
    <div>
      <SayfaBasligi
        baslik="Yöneticiler"
        aciklama={liste ? `${liste.length} yönetici hesabı` : "Panele tam erişimi olan hesaplar"}
        eylemler={<button onClick={() => setYeniAcik(true)} className={birincilDugme}>Yeni yönetici</button>}
      />

      {hata && <p role="alert" className="text-[13px] text-hata mb-3">{hata}</p>}

      {!liste ? (
        <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>
      ) : (
        <>
          <div className="hidden md:block bg-yuzey border border-cizgi rounded-[14px] overflow-hidden">
            <table className="w-full text-[13px]">
              <thead>
                <tr>
                  <th className={th}>Ad soyad</th>
                  <th className={th}>Giriş bilgisi</th>
                  <th className={th}>Son giriş</th>
                  <th className={th}>Durum</th>
                  <th className={th}></th>
                </tr>
              </thead>
              <tbody>
                {liste.map((y) => (
                  <tr key={y.id} className={satir}>
                    <td className={`${td} font-medium`}>{y.ad_soyad ?? "—"}{siz(y)}</td>
                    <td className={`${td} text-metin-soluk`}>{girisiBicimle(y.giris)}</td>
                    <td className={`${td} text-metin-soluk`}>{sonGiris(y.son_giris)}</td>
                    <td className={td}><AktifRozeti aktif={y.aktif} /></td>
                    <td className="px-4 py-1.5">
                      <div className="flex gap-2 justify-end flex-wrap">{eylemler(y)}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="md:hidden space-y-2">
            {liste.map((y) => (
              <li key={y.id} className="bg-yuzey border border-cizgi rounded-[14px] p-4 text-[13px]">
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium">{y.ad_soyad ?? y.giris}{siz(y)}</span>
                  <AktifRozeti aktif={y.aktif} />
                </div>
                <div className="text-metin-soluk mt-1 break-all">{girisiBicimle(y.giris)}</div>
                <div className="text-metin-soluk">Son giriş: {sonGiris(y.son_giris)}</div>
                {y.ben && <div className="mt-1 text-[12px] text-metin-soluk">{KENDI_NOTU}.</div>}
                <div className="flex gap-2 flex-wrap mt-3">{eylemler(y)}</div>
              </li>
            ))}
          </ul>
        </>
      )}

      {yeniAcik && (
        <YeniYonetici
          onKapat={() => setYeniAcik(false)}
          onOlustu={(deger, y) => {
            setYeniAcik(false);
            setSifre({ baslik: `${adi(y)} için geçici şifre`, deger, giris: y.giris });
            void yukle();
          }}
        />
      )}
      {duzenlenen && (
        <Duzenle
          yonetici={duzenlenen}
          onKapat={() => setDuzenlenen(null)}
          onKaydedildi={() => {
            setDuzenlenen(null);
            void yukle();
          }}
        />
      )}
      {sifre && (
        <GeciciSifreKutusu
          sifre={sifre.deger}
          baslik={sifre.baslik}
          giris={sifre.giris}
          telefon={sifre.giris.includes("@") ? null : sifre.giris}
          uyari="Bu şifre yalnızca şimdi görünür. Yöneticiye güvenli bir yoldan iletin; ilk girişte yeni şifre belirleyecek."
          onKapat={() => setSifre(null)}
        />
      )}
    </div>
  );
}

function Modal({ baslik, children, onKapat }: { baslik: string; children: React.ReactNode; onKapat: () => void }) {
  return (
    <div className="fixed inset-0 z-30 bg-black/70 grid place-items-center p-4" role="dialog" aria-modal="true" aria-label={baslik}>
      <div className="w-full max-w-md bg-yuzey border border-cizgi-guclu rounded-[14px]">
        <div className="flex items-center justify-between px-4 min-h-11 border-b border-cizgi">
          <h2 className="font-display text-[19px] leading-6">{baslik}</h2>
          <button onClick={onKapat} className="px-2 min-h-11 text-[13px] text-metin-soluk hover:text-metin" aria-label="Kapat">Kapat</button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}

function YeniYonetici({ onKapat, onOlustu }: { onKapat: () => void; onOlustu: (sifre: string, y: YoneticiOzet) => void }) {
  const [ad, setAd] = useState("");
  const [giris, setGiris] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    if (!ad.trim() || !giris.trim()) return setHata("Ad soyad ve giriş bilgisi zorunludur.");
    setGonderiliyor(true);
    setHata(null);
    try {
      const y = await yoneticiOlustur({ ad_soyad: ad.trim(), giris: giris.trim() });
      onOlustu(y.gecici_sifre, y.yonetici);
    } catch (err) {
      setHata(hataMesaji(err));
      setGonderiliyor(false);
    }
  }

  return (
    <Modal baslik="Yeni yönetici" onKapat={onKapat}>
      <form onSubmit={gonder} noValidate className="space-y-3">
        <label className="block"><span className="text-[13px] text-metin-soluk">Ad soyad</span>
          <input className={girdi} value={ad} onChange={(e) => setAd(e.target.value)} autoFocus /></label>
        <label className="block"><span className="text-[13px] text-metin-soluk">Giriş (e-posta veya telefon)</span>
          <input className={girdi} value={giris} onChange={(e) => setGiris(e.target.value)} autoCapitalize="none" /></label>
        <p className="text-[12px] text-metin-soluk">Geçici şifre oluşturulur ve bir kez gösterilir. Yeni yönetici ilk girişte kendi şifresini belirler.</p>
        {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
        <button type="submit" disabled={gonderiliyor} className={birincilDugme}>
          {gonderiliyor ? "Oluşturuluyor…" : "Oluştur"}
        </button>
      </form>
    </Modal>
  );
}

function Duzenle({ yonetici, onKapat, onKaydedildi }: { yonetici: YoneticiOzet; onKapat: () => void; onKaydedildi: () => void }) {
  const [ad, setAd] = useState(yonetici.ad_soyad ?? "");
  const [giris, setGiris] = useState(yonetici.giris);
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);
  const girisDegisti = !yonetici.ben && giris.trim().toLowerCase() !== yonetici.giris;

  async function gonder(e: FormEvent) {
    e.preventDefault();
    if (!ad.trim()) return setHata("Ad soyad zorunludur.");
    if (!giris.trim()) return setHata("Giriş bilgisi boş olamaz.");
    setGonderiliyor(true);
    setHata(null);
    try {
      await yoneticiGuncelle(yonetici.id, { ad_soyad: ad.trim(), ...(girisDegisti ? { giris: giris.trim() } : {}) });
      onKaydedildi();
    } catch (err) {
      setHata(hataMesaji(err));
      setGonderiliyor(false);
    }
  }

  return (
    <Modal baslik="Yöneticiyi düzenle" onKapat={onKapat}>
      <form onSubmit={gonder} noValidate className="space-y-3">
        <label className="block"><span className="text-[13px] text-metin-soluk">Ad soyad</span>
          <input className={girdi} value={ad} onChange={(e) => setAd(e.target.value)} autoFocus /></label>
        <label className="block"><span className="text-[13px] text-metin-soluk">Giriş (e-posta veya telefon)</span>
          <input className={`${girdi} ${yonetici.ben ? "opacity-70" : ""}`} value={giris} onChange={(e) => setGiris(e.target.value)} autoCapitalize="none" readOnly={yonetici.ben} />
          {yonetici.ben ? (
            <span className="block mt-1 text-[12px] text-metin-soluk">Kendi girişinizi Ayarlar &gt; Hesabım bölümünden değiştirebilirsiniz.</span>
          ) : girisDegisti ? (
            <span className="block mt-1 text-[12px] text-metin-soluk">Giriş değişince yöneticinin açık oturumları kapanır.</span>
          ) : null}
        </label>
        {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
        <button type="submit" disabled={gonderiliyor} className={birincilDugme}>
          {gonderiliyor ? "Kaydediliyor…" : "Kaydet"}
        </button>
      </form>
    </Modal>
  );
}
