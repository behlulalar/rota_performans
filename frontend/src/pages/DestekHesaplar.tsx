import { useCallback, useEffect, useState } from "react";
import {
  hesabiAktifeAl, hesabiPasifeAl, hesapSifreSifirla, hesaplariGetir, kilidiAc, oturumlariGetir, oturumlariKapat,
  ROL_ETIKET, type HesapListesi, type HesapSatiri, type OturumSatiri,
} from "../api/destek";
import GeciciSifreKutusu from "../components/GeciciSifreKutusu";
import Modal from "../components/Modal";
import { useOnay } from "../components/OnayPenceresi";
import SayfaBasligi from "../components/SayfaBasligi";
import { hataMesaji } from "../lib/dogrulama";
import { girisiBicimle } from "../lib/hatirla";
import { dugme, rozetBasari, rozetBirincil, rozetHata, rozetNotr, rozetUyari, satir, secimKutusu, td, th } from "../lib/stil";

const BOYUT = 20;

const zaman = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "Henüz girmedi";

const adi = (h: HesapSatiri) => h.ad_soyad || h.giris;

function Rozetler({ h }: { h: HesapSatiri }) {
  return (
    <span className="inline-flex flex-wrap gap-1.5">
      <span className={h.rol === "destek" ? rozetBirincil : rozetNotr}>{ROL_ETIKET[h.rol]}</span>
      {!h.aktif && <span className={rozetNotr}>Pasif</span>}
      {h.kilitli && <span className={rozetHata}>Kilitli</span>}
      {h.rol === "destek" && <span className={h.totp_aktif ? rozetBasari : rozetUyari}>{h.totp_aktif ? "2FA açık" : "2FA kurulmadı"}</span>}
      {h.ben && <span className={rozetNotr}>siz</span>}
    </span>
  );
}

export default function DestekHesaplar() {
  const onayla = useOnay();
  const [arama, setArama] = useState("");
  const [q, setQ] = useState("");
  const [rol, setRol] = useState("");
  const [sayfa, setSayfa] = useState(1);
  const [veri, setVeri] = useState<HesapListesi | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<string | null>(null);
  const [islemHatasi, setIslemHatasi] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const [surum, setSurum] = useState(0);
  const [sifre, setSifre] = useState<{ ad: string; giris: string; deger: string } | null>(null);
  const [oturumHesabi, setOturumHesabi] = useState<HesapSatiri | null>(null);

  useEffect(() => {
    const t = setTimeout(() => { setQ(arama.trim()); setSayfa(1); }, 300);
    return () => clearTimeout(t);
  }, [arama]);

  useEffect(() => {
    let iptal = false;
    setYukleniyor(true);
    setHata(null);
    hesaplariGetir({ q, rol, sayfa, boyut: BOYUT })
      .then((v) => !iptal && setVeri(v))
      .catch((e) => !iptal && setHata(hataMesaji(e)))
      .finally(() => !iptal && setYukleniyor(false));
    return () => { iptal = true; };
  }, [q, rol, sayfa, surum]);

  const yenile = useCallback(() => setSurum((s) => s + 1), []);

  async function islem(is: () => Promise<void>) {
    setMesgul(true);
    setIslemHatasi(null);
    try {
      await is();
    } catch (e) {
      setIslemHatasi(hataMesaji(e));
    } finally {
      setMesgul(false);
    }
  }

  const kilitAc = (h: HesapSatiri) =>
    islem(async () => {
      await kilidiAc(h.id);
      yenile();
    });

  const sifirla = (h: HesapSatiri) =>
    islem(async () => {
      if (!(await onayla({ baslik: "Şifre sıfırla", mesaj: `${adi(h)} için şifre sıfırlansın mı? Eski şifre geçersiz olur, açık oturumları kapanır.`, onayYazisi: "Sıfırla" }))) return;
      const r = await hesapSifreSifirla(h.id);
      setSifre({ ad: adi(h), giris: h.giris, deger: r.gecici_sifre });
      yenile();
    });

  const durumDegistir = (h: HesapSatiri) =>
    islem(async () => {
      const onay = await onayla({
        baslik: h.aktif ? "Pasife al" : "Aktif et",
        mesaj: h.aktif ? `${adi(h)} pasife alınsın mı? Açık oturumları kapanır ve giriş yapamaz.` : `${adi(h)} tekrar aktif edilsin mi?`,
        onayYazisi: h.aktif ? "Pasife al" : "Aktif et",
        tehlikeli: h.aktif,
      });
      if (!onay) return;
      await (h.aktif ? hesabiPasifeAl(h.id) : hesabiAktifeAl(h.id));
      yenile();
    });

  const eylemler = (h: HesapSatiri) => (
    <>
      {h.kilitli && <button className={dugme} disabled={mesgul} onClick={() => void kilitAc(h)}>Kilidi aç</button>}
      <button className={dugme} disabled={mesgul || h.ben} title={h.ben ? "Kendi şifrenizi Ayarlar > Hesabım bölümünden değiştirin" : undefined} onClick={() => void sifirla(h)}>Şifre sıfırla</button>
      <button className={dugme} disabled={mesgul || (h.ben && h.aktif)} title={h.ben ? "Kendi hesabınızı pasife alamazsınız" : undefined} onClick={() => void durumDegistir(h)}>{h.aktif ? "Pasife al" : "Aktif et"}</button>
      <button className={dugme} onClick={() => setOturumHesabi(h)}>Oturumlar</button>
    </>
  );

  const sayfaSayisi = veri ? Math.max(1, Math.ceil(veri.toplam / veri.boyut)) : 1;

  return (
    <div className="space-y-6">
      <SayfaBasligi baslik="Hesaplar" aciklama={veri ? `${veri.toplam} hesap` : "Tüm rollerdeki panel hesapları"} />

      <div className="flex flex-wrap gap-3">
        <select value={rol} onChange={(e) => { setRol(e.target.value); setSayfa(1); }} aria-label="Rol filtresi" className={secimKutusu}>
          <option value="">Tüm roller</option>
          {Object.entries(ROL_ETIKET).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input type="search" value={arama} onChange={(e) => setArama(e.target.value)} placeholder="Ad, e-posta veya telefon ara…" aria-label="Hesap ara" className={`${secimKutusu} flex-1 min-w-48 max-w-sm`} />
      </div>

      {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
      {islemHatasi && <p role="alert" className="text-[13px] text-hata">{islemHatasi}</p>}
      {!veri ? (
        !hata && <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>
      ) : veri.kayitlar.length === 0 ? (
        <div className="bg-yuzey border border-cizgi rounded-[14px] p-10 text-center text-metin-soluk">Bu filtrede hesap yok.</div>
      ) : (
        <div className={yukleniyor ? "opacity-60" : ""}>
          <div className="hidden md:block bg-yuzey border border-cizgi rounded-[14px] overflow-hidden">
            <table className="w-full text-[13px]" aria-label="Hesaplar">
              <thead><tr>
                <th className={th}>Hesap</th><th className={th}>Durum</th><th className={th}>Son giriş</th><th className={th}></th>
              </tr></thead>
              <tbody>
                {veri.kayitlar.map((h) => (
                  <tr key={h.id} className={`${satir} align-top`}>
                    <td className={`${td} py-2`}>
                      <div className="font-medium">{h.ad_soyad ?? "—"}</div>
                      <div className="text-xs text-metin-soluk break-all">{girisiBicimle(h.giris)}</div>
                    </td>
                    <td className={`${td} py-2`}><Rozetler h={h} /></td>
                    <td className={`${td} py-2 num whitespace-nowrap text-metin-soluk`}>{zaman(h.son_giris)}</td>
                    <td className="px-4 py-1.5"><div className="flex gap-2 justify-end flex-wrap">{eylemler(h)}</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="md:hidden space-y-2">
            {veri.kayitlar.map((h) => (
              <li key={h.id} className="bg-yuzey border border-cizgi rounded-[14px] p-4 space-y-1.5 text-[13px]">
                <div className="font-medium">{h.ad_soyad ?? h.giris}</div>
                <div className="text-metin-soluk break-all">{girisiBicimle(h.giris)}</div>
                <Rozetler h={h} />
                <div className="num text-metin-soluk">Son giriş: {zaman(h.son_giris)}</div>
                <div className="flex gap-2 flex-wrap pt-1.5">{eylemler(h)}</div>
              </li>
            ))}
          </ul>

          <div className="flex items-center justify-between gap-3 mt-4 text-[13px]">
            <span className="text-metin-soluk num">{veri.toplam} kayıt · Sayfa {veri.sayfa} / {sayfaSayisi}</span>
            <div className="flex gap-2">
              <button className={dugme} disabled={sayfa <= 1} onClick={() => setSayfa((s) => s - 1)}>Önceki</button>
              <button className={dugme} disabled={sayfa >= sayfaSayisi} onClick={() => setSayfa((s) => s + 1)}>Sonraki</button>
            </div>
          </div>
        </div>
      )}

      {sifre && (
        <GeciciSifreKutusu
          sifre={sifre.deger}
          baslik={`${sifre.ad} için yeni geçici şifre`}
          giris={sifre.giris}
          uyari="Bu şifre yalnızca şimdi görünür. Hesap sahibine güvenli bir yoldan iletin; ilk girişte yeni şifre belirleyecek."
          onKapat={() => setSifre(null)}
        />
      )}
      {oturumHesabi && <Oturumlar hesap={oturumHesabi} onKapat={() => setOturumHesabi(null)} />}
    </div>
  );
}

function Oturumlar({ hesap, onKapat }: { hesap: HesapSatiri; onKapat: () => void }) {
  const onayla = useOnay();
  const [liste, setListe] = useState<OturumSatiri[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [mesaj, setMesaj] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);

  const yukle = useCallback(async () => {
    try {
      setListe(await oturumlariGetir(hesap.id));
    } catch (e) {
      setHata(hataMesaji(e));
    }
  }, [hesap.id]);

  useEffect(() => {
    void yukle();
  }, [yukle]);

  async function hepsiniKapat() {
    if (!(await onayla({ baslik: "Oturumları kapat", mesaj: `${adi(hesap)} hesabının tüm açık oturumları kapatılsın mı?`, onayYazisi: "Tümünü kapat", tehlikeli: true }))) return;
    setMesgul(true);
    setHata(null);
    try {
      const r = await oturumlariKapat(hesap.id);
      setMesaj(`${r.kapatilan} oturum kapatıldı.`);
      await yukle();
    } catch (e) {
      setHata(hataMesaji(e));
    } finally {
      setMesgul(false);
    }
  }

  const aktifSayisi = liste?.filter((o) => o.aktif).length ?? 0;

  return (
    <Modal baslik={`${adi(hesap)} oturumları`} onKapat={onKapat}>
      <div className="space-y-3">
        {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
        {mesaj && <p role="status" className="text-[13px] text-basari">{mesaj}</p>}
        {!liste ? (
          !hata && <p className="py-6 text-center text-metin-soluk">Yükleniyor…</p>
        ) : liste.length === 0 ? (
          <p className="py-6 text-center text-metin-soluk">Bu hesabın oturumu yok.</p>
        ) : (
          <ul className="border border-cizgi rounded-[10px] divide-y divide-cizgi text-[13px]" aria-label="Oturumlar">
            {liste.map((o) => (
              <li key={o.id} className="flex items-start justify-between gap-3 px-3 py-2">
                <div className="min-w-0">
                  <div className="num">{zaman(o.olusturma)}</div>
                  <div className="num text-xs text-metin-soluk">Bitiş: {zaman(o.bitis)}{o.hatirla && " · Beni hatırla"}</div>
                </div>
                <span className={o.aktif ? rozetBasari : rozetNotr}>{o.aktif ? "Açık" : "Kapalı"}</span>
              </li>
            ))}
          </ul>
        )}
        <div className="flex justify-end">
          <button className={dugme} disabled={mesgul || aktifSayisi === 0} onClick={() => void hepsiniKapat()}>Tümünü kapat</button>
        </div>
      </div>
    </Modal>
  );
}
