import { useCallback, useEffect, useState, type FormEvent } from "react";
import TelefonGirdisi from "../components/TelefonGirdisi";
import { apiyeCevir, bicimle, gecerliMi, numaraCoz, TELEFON_HATA, telefonSec } from "../lib/telefon";
import {
  antrenorGuncelle,
  antrenorleriGetir,
  antrenorOlustur,
  sifreSifirla,
  type AntrenorOzet,
} from "../api/antrenor";
import GeciciSifreKutusu from "../components/GeciciSifreKutusu";
import { hataMesaji } from "../lib/dogrulama";
import SayfaBasligi from "../components/SayfaBasligi";
import { birincilDugme, dugme, girdi, rozetBasari, rozetNotr, satir, secimKutusu, td, th } from "../lib/stil";
import { useOnay } from "../components/OnayPenceresi";


function AktifRozeti({ aktif }: { aktif: boolean }) {
  return <span className={aktif ? rozetBasari : rozetNotr}>{aktif ? "Aktif" : "Pasif"}</span>;
}

export default function AntrenorListe() {
  const onayla = useOnay();
  const [filtre, setFiltre] = useState("");
  const [liste, setListe] = useState<AntrenorOzet[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const [sifre, setSifre] = useState<{ baslik: string; deger: string; giris?: string | null; telefon?: string | null } | null>(null);
  const [yeniAcik, setYeniAcik] = useState(false);
  const [duzenlenen, setDuzenlenen] = useState<AntrenorOzet | null>(null);

  const yukle = useCallback(async () => {
    try {
      setListe(await antrenorleriGetir(filtre === "" ? undefined : filtre === "aktif"));
    } catch (e) {
      setHata(hataMesaji(e));
    }
  }, [filtre]);

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

  const durumDegistir = (a: AntrenorOzet) =>
    islem(async () => {
      if (!(await onayla({ baslik: a.aktif ? "Pasife al" : "Aktif et", mesaj: a.aktif ? `${a.ad_soyad} pasife alınsın mı?` : `${a.ad_soyad} tekrar aktif edilsin mi?`, onayYazisi: a.aktif ? "Pasife al" : "Aktif et" }))) return;
      await antrenorGuncelle(a.id, { aktif: !a.aktif });
      await yukle();
    });

  const sifirla = (a: AntrenorOzet) =>
    islem(async () => {
      if (!(await onayla({ baslik: "Şifre sıfırla", mesaj: `${a.ad_soyad} için şifre sıfırlansın mı? Eski şifre geçersiz olur.`, onayYazisi: "Sıfırla" }))) return;
      const y = await sifreSifirla(a.id);
      setSifre({ baslik: `${a.ad_soyad} için yeni geçici şifre`, deger: y.gecici_sifre, giris: a.giris, telefon: telefonSec(a.giris, a.telefon) });
    });

  return (
    <div>
      <SayfaBasligi
        baslik="Antrenörler"
        aciklama={liste ? `${liste.length} antrenör listeleniyor` : "Antrenör hesapları ve grup atamaları"}
        eylemler={<button onClick={() => setYeniAcik(true)} className={birincilDugme}>Yeni antrenör</button>}
      />

      <div className="mb-4">
        <select
          value={filtre}
          onChange={(e) => setFiltre(e.target.value)}
          aria-label="Durum filtresi"
          className={secimKutusu}
        >
          <option value="">Tüm durumlar</option>
          <option value="aktif">Aktif</option>
          <option value="pasif">Pasif</option>
        </select>
      </div>

      {hata && <p role="alert" className="text-[13px] text-hata mb-3">{hata}</p>}

      {!liste ? (
        <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>
      ) : liste.length === 0 ? (
        <div className="bg-yuzey border border-cizgi rounded-[14px] p-10 text-center text-metin-soluk">Antrenör bulunamadı.</div>
      ) : (
        <>
          <div className="hidden md:block bg-yuzey border border-cizgi rounded-[14px] overflow-hidden">
            <table className="w-full text-[13px]">
              <thead>
                <tr>
                  <th className={th}>Ad soyad</th>
                  <th className={th}>Telefon</th>
                  <th className={th}>Giriş bilgisi</th>
                  <th className={th}>Grup</th>
                  <th className={th}>Durum</th>
                  <th className={th}></th>
                </tr>
              </thead>
              <tbody>
                {liste.map((a) => (
                  <tr key={a.id} className={satir}>
                    <td className={`${td} font-medium`}>{a.ad_soyad}</td>
                    <td className={`${td} num text-metin-soluk`}>{a.telefon ? bicimle(a.telefon) : "—"}</td>
                    <td className={`${td} text-metin-soluk`}>{a.giris ?? "—"}</td>
                    <td className={`${td} num`}>{a.grup_sayisi}</td>
                    <td className={td}><AktifRozeti aktif={a.aktif} /></td>
                    <td className="px-4 py-1.5">
                      <div className="flex gap-2 justify-end flex-wrap">
                        <button className={dugme} onClick={() => setDuzenlenen(a)}>Düzenle</button>
                        <button className={dugme} disabled={mesgul} onClick={() => void sifirla(a)}>Şifre sıfırla</button>
                        <button className={dugme} disabled={mesgul} onClick={() => void durumDegistir(a)}>{a.aktif ? "Pasife al" : "Aktif et"}</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="md:hidden space-y-2">
            {liste.map((a) => (
              <li key={a.id} className="bg-yuzey border border-cizgi rounded-[14px] p-4 text-[13px]">
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium">{a.ad_soyad}</span>
                  <AktifRozeti aktif={a.aktif} />
                </div>
                <div className="num text-metin-soluk mt-1">{a.telefon ? bicimle(a.telefon) : "Telefon yok"} · {a.giris ?? "Giriş yok"}</div>
                <div className="num text-metin-soluk">{a.grup_sayisi} grup</div>
                <div className="flex gap-2 flex-wrap mt-3">
                  <button className={dugme} onClick={() => setDuzenlenen(a)}>Düzenle</button>
                  <button className={dugme} disabled={mesgul} onClick={() => void sifirla(a)}>Şifre sıfırla</button>
                  <button className={dugme} disabled={mesgul} onClick={() => void durumDegistir(a)}>{a.aktif ? "Pasife al" : "Aktif et"}</button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      {yeniAcik && (
        <YeniAntrenor
          onKapat={() => setYeniAcik(false)}
          onOlustu={(deger, ad, giris, telefon) => {
            setYeniAcik(false);
            setSifre({ baslik: `${ad} için geçici şifre`, deger, giris, telefon: telefonSec(giris, telefon) });
            void yukle();
          }}
        />
      )}
      {duzenlenen && (
        <Duzenle
          antrenor={duzenlenen}
          onKapat={() => setDuzenlenen(null)}
          onKaydedildi={() => {
            setDuzenlenen(null);
            void yukle();
          }}
        />
      )}
      {sifre && <GeciciSifreKutusu sifre={sifre.deger} baslik={sifre.baslik} giris={sifre.giris} telefon={sifre.telefon} onKapat={() => setSifre(null)} />}
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

function YeniAntrenor({ onKapat, onOlustu }: { onKapat: () => void; onOlustu: (sifre: string, ad: string, giris: string | null, telefon: string | null) => void }) {
  const [ad, setAd] = useState("");
  const [telefon, setTelefon] = useState("");
  const [giris, setGiris] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    if (!ad.trim() || !giris.trim()) return setHata("Ad soyad ve giriş bilgisi zorunludur.");
    if (telefon && !gecerliMi(telefon)) return setHata(TELEFON_HATA);
    setGonderiliyor(true);
    setHata(null);
    try {
      const y = await antrenorOlustur({ ad_soyad: ad.trim(), telefon: apiyeCevir(telefon) ?? undefined, giris: giris.trim() });
      onOlustu(y.gecici_sifre, y.antrenor.ad_soyad, y.antrenor.giris, y.antrenor.telefon);
    } catch (err) {
      setHata(hataMesaji(err));
      setGonderiliyor(false);
    }
  }

  return (
    <Modal baslik="Yeni antrenör" onKapat={onKapat}>
      <form onSubmit={gonder} noValidate className="space-y-3">
        <label className="block"><span className="text-[13px] text-metin-soluk">Ad soyad</span>
          <input className={girdi} value={ad} onChange={(e) => setAd(e.target.value)} autoFocus /></label>
        <label className="block"><span className="text-[13px] text-metin-soluk">Telefon</span>
          <TelefonGirdisi value={telefon} onChange={setTelefon} /></label>
        <label className="block"><span className="text-[13px] text-metin-soluk">Giriş (e-posta veya telefon)</span>
          <input className={girdi} value={giris} onChange={(e) => setGiris(e.target.value)} autoCapitalize="none" /></label>
        {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
        <button type="submit" disabled={gonderiliyor} className={birincilDugme}>
          {gonderiliyor ? "Oluşturuluyor…" : "Oluştur"}
        </button>
      </form>
    </Modal>
  );
}

function Duzenle({ antrenor, onKapat, onKaydedildi }: { antrenor: AntrenorOzet; onKapat: () => void; onKaydedildi: () => void }) {
  const [ad, setAd] = useState(antrenor.ad_soyad);
  const [telefon, setTelefon] = useState(numaraCoz(antrenor.telefon));
  const [giris, setGiris] = useState(antrenor.giris ?? "");
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);
  const girisDegisti = antrenor.giris !== null && giris.trim().toLowerCase() !== antrenor.giris;

  async function gonder(e: FormEvent) {
    e.preventDefault();
    if (!ad.trim()) return setHata("Ad soyad zorunludur.");
    if (antrenor.giris !== null && !giris.trim()) return setHata("Giriş bilgisi boş olamaz.");
    if (telefon && !gecerliMi(telefon)) return setHata(TELEFON_HATA);
    setGonderiliyor(true);
    setHata(null);
    try {
      await antrenorGuncelle(antrenor.id, {
        ad_soyad: ad.trim(),
        telefon: apiyeCevir(telefon) ?? undefined,
        ...(girisDegisti ? { giris: giris.trim() } : {}),
      });
      onKaydedildi();
    } catch (err) {
      setHata(hataMesaji(err));
      setGonderiliyor(false);
    }
  }

  return (
    <Modal baslik="Antrenörü düzenle" onKapat={onKapat}>
      <form onSubmit={gonder} noValidate className="space-y-3">
        <label className="block"><span className="text-[13px] text-metin-soluk">Ad soyad</span>
          <input className={girdi} value={ad} onChange={(e) => setAd(e.target.value)} autoFocus /></label>
        <label className="block"><span className="text-[13px] text-metin-soluk">Telefon</span>
          <TelefonGirdisi value={telefon} onChange={setTelefon} /></label>
        {antrenor.giris !== null && (
          <label className="block"><span className="text-[13px] text-metin-soluk">Giriş (e-posta veya telefon)</span>
            <input className={girdi} value={giris} onChange={(e) => setGiris(e.target.value)} autoCapitalize="none" />
            {girisDegisti && (
              <span className="block mt-1 text-[12px] text-metin-soluk">Giriş değişince antrenörün açık oturumları kapanır; yeni girişle tekrar girmesi gerekir.</span>
            )}
          </label>
        )}
        {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
        <button type="submit" disabled={gonderiliyor} className={birincilDugme}>
          {gonderiliyor ? "Kaydediliyor…" : "Kaydet"}
        </button>
      </form>
    </Modal>
  );
}
