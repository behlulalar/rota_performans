import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  antrenorGuncelle,
  antrenorleriGetir,
  antrenorOlustur,
  sifreSifirla,
  type AntrenorOzet,
} from "../api/antrenor";
import GeciciSifreKutusu from "../components/GeciciSifreKutusu";
import { hataMesaji } from "../lib/dogrulama";

const girdi = "mt-1 w-full rounded-lg bg-zemin border border-cizgi px-3 py-2.5 outline-none focus:border-altin";
const dugme = "rounded-lg border border-cizgi px-3 py-1.5 text-sm hover:border-altin disabled:opacity-50";

function AktifRozeti({ aktif }: { aktif: boolean }) {
  return (
    <span className={`inline-block rounded-full border px-2.5 py-0.5 text-xs ${aktif ? "border-basari/50 text-basari" : "border-cizgi text-metin-soluk"}`}>
      {aktif ? "Aktif" : "Pasif"}
    </span>
  );
}

export default function AntrenorListe() {
  const [filtre, setFiltre] = useState("");
  const [liste, setListe] = useState<AntrenorOzet[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const [sifre, setSifre] = useState<{ baslik: string; deger: string } | null>(null);
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
      if (!window.confirm(a.aktif ? `${a.ad_soyad} pasife alınsın mı?` : `${a.ad_soyad} tekrar aktif edilsin mi?`)) return;
      await antrenorGuncelle(a.id, { aktif: !a.aktif });
      await yukle();
    });

  const sifirla = (a: AntrenorOzet) =>
    islem(async () => {
      if (!window.confirm(`${a.ad_soyad} için şifre sıfırlansın mı? Eski şifre geçersiz olur.`)) return;
      const y = await sifreSifirla(a.id);
      setSifre({ baslik: `${a.ad_soyad} için yeni geçici şifre`, deger: y.gecici_sifre });
    });

  return (
    <div>
      <div className="flex items-center justify-between gap-3 mb-4">
        <h1 className="text-xl font-semibold">Antrenörler</h1>
        <button onClick={() => setYeniAcik(true)} className="rounded-lg bg-altin text-zemin font-semibold px-4 py-2 text-sm hover:bg-altin-acik">
          Yeni antrenör
        </button>
      </div>

      <div className="mb-4">
        <select
          value={filtre}
          onChange={(e) => setFiltre(e.target.value)}
          aria-label="Durum filtresi"
          className="rounded-lg bg-yuzey border border-cizgi px-3 py-2.5 outline-none focus:border-altin"
        >
          <option value="">Tüm durumlar</option>
          <option value="aktif">Aktif</option>
          <option value="pasif">Pasif</option>
        </select>
      </div>

      {hata && <p role="alert" className="text-sm text-hata mb-3">{hata}</p>}

      {!liste ? (
        <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>
      ) : liste.length === 0 ? (
        <div className="bg-yuzey border border-cizgi rounded-2xl p-10 text-center text-metin-soluk">Antrenör bulunamadı.</div>
      ) : (
        <>
          <div className="hidden md:block bg-yuzey border border-cizgi rounded-2xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="text-left text-metin-soluk border-b border-cizgi">
                <tr>
                  <th className="p-3">Ad soyad</th>
                  <th className="p-3">Telefon</th>
                  <th className="p-3">Giriş bilgisi</th>
                  <th className="p-3">Grup</th>
                  <th className="p-3">Durum</th>
                  <th className="p-3"></th>
                </tr>
              </thead>
              <tbody>
                {liste.map((a) => (
                  <tr key={a.id} className="border-b border-cizgi last:border-0">
                    <td className="p-3 font-medium">{a.ad_soyad}</td>
                    <td className="p-3 text-metin-soluk">{a.telefon ?? "—"}</td>
                    <td className="p-3 text-metin-soluk">{a.giris ?? "—"}</td>
                    <td className="p-3">{a.grup_sayisi}</td>
                    <td className="p-3"><AktifRozeti aktif={a.aktif} /></td>
                    <td className="p-3">
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

          <ul className="md:hidden space-y-3">
            {liste.map((a) => (
              <li key={a.id} className="bg-yuzey border border-cizgi rounded-2xl p-3 text-sm">
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium">{a.ad_soyad}</span>
                  <AktifRozeti aktif={a.aktif} />
                </div>
                <div className="text-metin-soluk mt-1">{a.telefon ?? "Telefon yok"} · {a.giris ?? "Giriş yok"}</div>
                <div className="text-metin-soluk">{a.grup_sayisi} grup</div>
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
          onOlustu={(deger, ad) => {
            setYeniAcik(false);
            setSifre({ baslik: `${ad} için geçici şifre`, deger });
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
      {sifre && <GeciciSifreKutusu sifre={sifre.deger} baslik={sifre.baslik} onKapat={() => setSifre(null)} />}
    </div>
  );
}

function Modal({ baslik, children, onKapat }: { baslik: string; children: React.ReactNode; onKapat: () => void }) {
  return (
    <div className="fixed inset-0 z-30 bg-black/70 grid place-items-center p-4" role="dialog" aria-modal="true" aria-label={baslik}>
      <div className="w-full max-w-md bg-yuzey border border-cizgi rounded-2xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">{baslik}</h2>
          <button onClick={onKapat} className="text-sm text-metin-soluk hover:text-metin" aria-label="Kapat">Kapat</button>
        </div>
        {children}
      </div>
    </div>
  );
}

function YeniAntrenor({ onKapat, onOlustu }: { onKapat: () => void; onOlustu: (sifre: string, ad: string) => void }) {
  const [ad, setAd] = useState("");
  const [telefon, setTelefon] = useState("");
  const [giris, setGiris] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    if (!ad.trim() || !giris.trim()) return setHata("Ad soyad ve giriş bilgisi zorunludur.");
    setGonderiliyor(true);
    setHata(null);
    try {
      const y = await antrenorOlustur({ ad_soyad: ad.trim(), telefon: telefon.trim() || undefined, giris: giris.trim() });
      onOlustu(y.gecici_sifre, y.antrenor.ad_soyad);
    } catch (err) {
      setHata(hataMesaji(err));
      setGonderiliyor(false);
    }
  }

  return (
    <Modal baslik="Yeni antrenör" onKapat={onKapat}>
      <form onSubmit={gonder} noValidate className="space-y-3">
        <label className="block"><span className="text-sm text-metin-soluk">Ad soyad</span>
          <input className={girdi} value={ad} onChange={(e) => setAd(e.target.value)} autoFocus /></label>
        <label className="block"><span className="text-sm text-metin-soluk">Telefon</span>
          <input className={girdi} type="tel" value={telefon} onChange={(e) => setTelefon(e.target.value)} /></label>
        <label className="block"><span className="text-sm text-metin-soluk">Giriş (e-posta veya telefon)</span>
          <input className={girdi} value={giris} onChange={(e) => setGiris(e.target.value)} autoCapitalize="none" /></label>
        {hata && <p role="alert" className="text-sm text-hata">{hata}</p>}
        <button type="submit" disabled={gonderiliyor} className="rounded-lg bg-altin text-zemin font-semibold px-5 py-2.5 hover:bg-altin-acik disabled:opacity-50">
          {gonderiliyor ? "Oluşturuluyor…" : "Oluştur"}
        </button>
      </form>
    </Modal>
  );
}

function Duzenle({ antrenor, onKapat, onKaydedildi }: { antrenor: AntrenorOzet; onKapat: () => void; onKaydedildi: () => void }) {
  const [ad, setAd] = useState(antrenor.ad_soyad);
  const [telefon, setTelefon] = useState(antrenor.telefon ?? "");
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    if (!ad.trim()) return setHata("Ad soyad zorunludur.");
    setGonderiliyor(true);
    setHata(null);
    try {
      await antrenorGuncelle(antrenor.id, { ad_soyad: ad.trim(), telefon: telefon.trim() });
      onKaydedildi();
    } catch (err) {
      setHata(hataMesaji(err));
      setGonderiliyor(false);
    }
  }

  return (
    <Modal baslik="Antrenörü düzenle" onKapat={onKapat}>
      <form onSubmit={gonder} noValidate className="space-y-3">
        <label className="block"><span className="text-sm text-metin-soluk">Ad soyad</span>
          <input className={girdi} value={ad} onChange={(e) => setAd(e.target.value)} autoFocus /></label>
        <label className="block"><span className="text-sm text-metin-soluk">Telefon</span>
          <input className={girdi} type="tel" value={telefon} onChange={(e) => setTelefon(e.target.value)} /></label>
        {hata && <p role="alert" className="text-sm text-hata">{hata}</p>}
        <button type="submit" disabled={gonderiliyor} className="rounded-lg bg-altin text-zemin font-semibold px-5 py-2.5 hover:bg-altin-acik disabled:opacity-50">
          {gonderiliyor ? "Kaydediliyor…" : "Kaydet"}
        </button>
      </form>
    </Modal>
  );
}
