import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import TelefonGirdisi from "../components/TelefonGirdisi";
import { apiyeCevir, bicimle, gecerliMi, numaraCoz, TELEFON_HATA, telefonSec } from "../lib/telefon";
import {
  antrenorFotoSil,
  antrenorFotoYukle,
  antrenorGuncelle,
  antrenorleriGetir,
  antrenorOlustur,
  sifreSifirla,
  type AntrenorOzet,
} from "../api/antrenor";
import AntrenorFoto from "../components/AntrenorFoto";
import FotoKirpma from "../components/FotoKirpma";
import { apiBlob } from "../lib/api";
import GeciciSifreKutusu from "../components/GeciciSifreKutusu";
import { gruplariGetir, type GrupOzet } from "../api/grup";
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
  const [surum, setSurum] = useState(0); // fotoğraf değişince avatarlar yeniden yüklenir

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
                  <th className={th}>Grup</th>
                  <th className={th}>Durum</th>
                  <th className={th}></th>
                </tr>
              </thead>
              <tbody>
                {liste.map((a) => (
                  <tr key={a.id} className={satir}>
                    <td className={`${td} font-medium`}>
                      <span className="inline-flex items-center gap-3">
                        <AntrenorFoto id={a.id} fotoVar={a.foto_var} adSoyad={a.ad_soyad} surum={surum} sinif="size-9 rounded-full" />
                        {a.ad_soyad}
                      </span>
                    </td>
                    <td className={`${td} num text-metin-soluk`}>{a.telefon ? bicimle(a.telefon) : "—"}</td>
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
                  <span className="inline-flex items-center gap-3 font-medium">
                    <AntrenorFoto id={a.id} fotoVar={a.foto_var} adSoyad={a.ad_soyad} surum={surum} sinif="size-9 rounded-full" />
                    {a.ad_soyad}
                  </span>
                  <AktifRozeti aktif={a.aktif} />
                </div>
                <div className="num text-metin-soluk mt-1">{a.telefon ? bicimle(a.telefon) : "Telefon yok"}</div>
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
          surum={surum}
          onFotoDegisti={() => {
            setSurum((s) => s + 1);
            void yukle();
          }}
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

function GrupSecici({ secili, onDegis, antrenorId }: { secili: string[]; onDegis: (idler: string[]) => void; antrenorId?: string }) {
  const [gruplar, setGruplar] = useState<GrupOzet[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    gruplariGetir(true).then(setGruplar, (e) => setHata(hataMesaji(e)));
  }, []);

  const degistir = (id: string, acik: boolean) => onDegis(acik ? [...secili, id] : secili.filter((x) => x !== id));

  return (
    <fieldset className="block">
      <legend className="text-[13px] text-metin-soluk">Gruplar</legend>
      {hata ? (
        <p role="alert" className="text-[13px] text-hata mt-1">{hata}</p>
      ) : !gruplar ? (
        <p className="text-[13px] text-metin-soluk mt-1">Yükleniyor…</p>
      ) : gruplar.length === 0 ? (
        <p className="text-[13px] text-metin-soluk mt-1">Henüz grup yok.</p>
      ) : (
        <ul className="mt-1 max-h-48 overflow-y-auto border border-cizgi rounded-lg divide-y divide-cizgi">
          {gruplar.map((g) => {
            const baskasi = g.antrenor && g.antrenor.id !== antrenorId ? g.antrenor.ad_soyad : null;
            return (
              <li key={g.id}>
                <label className="flex items-center gap-3 px-3 min-h-11 cursor-pointer text-[13px]">
                  <input type="checkbox" className="size-4 shrink-0" checked={secili.includes(g.id)} onChange={(e) => degistir(g.id, e.target.checked)} />
                  <span className="font-medium">{g.ad}</span>
                  {baskasi && <span className="text-metin-soluk text-[12px] ml-auto text-right">şu an: {baskasi}</span>}
                </label>
              </li>
            );
          })}
        </ul>
      )}
    </fieldset>
  );
}

function YeniAntrenor({ onKapat, onOlustu }: { onKapat: () => void; onOlustu: (sifre: string, ad: string, giris: string | null, telefon: string | null) => void }) {
  const [ad, setAd] = useState("");
  const [telefon, setTelefon] = useState("");
  const [gruplar, setGruplar] = useState<string[]>([]);
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    if (!ad.trim() || !telefon) return setHata("Ad soyad ve telefon zorunludur.");
    if (!gecerliMi(telefon)) return setHata(TELEFON_HATA);
    setGonderiliyor(true);
    setHata(null);
    try {
      const y = await antrenorOlustur({ ad_soyad: ad.trim(), telefon: apiyeCevir(telefon)!, grup_idleri: gruplar });
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
        <GrupSecici secili={gruplar} onDegis={setGruplar} />
        {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
        <button type="submit" disabled={gonderiliyor} className={birincilDugme}>
          {gonderiliyor ? "Oluşturuluyor…" : "Oluştur"}
        </button>
      </form>
    </Modal>
  );
}

function FotoBolumu({ antrenor, surum, onDegisti }: { antrenor: AntrenorOzet; surum: number; onDegisti: () => void }) {
  const onayla = useOnay();
  const dosyaGirdisi = useRef<HTMLInputElement>(null);
  const [fotoVar, setFotoVar] = useState(antrenor.foto_var);
  const [onay, setOnay] = useState(false);
  const [kirpilacak, setKirpilacak] = useState<Blob | null>(null);
  const [yerelSurum, setYerelSurum] = useState(0);
  const [mesgul, setMesgul] = useState(false);
  const [hata, setHata] = useState<string | null>(null);

  const fotoSec = (dosya: File | undefined) => {
    if (!dosya) return;
    if (!dosya.type.startsWith("image/")) return setHata("Lütfen bir görsel dosyası seçin.");
    setHata(null);
    setKirpilacak(dosya);
  };
  const kaydet = async (blob: Blob) => {
    await antrenorFotoYukle(antrenor.id, blob);
    setFotoVar(true);
    setYerelSurum((s) => s + 1);
    setKirpilacak(null);
    onDegisti();
  };
  async function ayarla() {
    setMesgul(true);
    setHata(null);
    try {
      setKirpilacak(await apiBlob(`/api/antrenorler/${antrenor.id}/foto?boyut=buyuk&v=${surum + yerelSurum}`));
    } catch (e) {
      setHata(hataMesaji(e));
    } finally {
      setMesgul(false);
    }
  }
  async function kaldir() {
    if (!(await onayla({ baslik: "Fotoğrafı sil", mesaj: "Fotoğraf silinsin mi?", onayYazisi: "Sil", tehlikeli: true }))) return;
    setMesgul(true);
    setHata(null);
    try {
      await antrenorFotoSil(antrenor.id);
      setFotoVar(false);
      setYerelSurum((s) => s + 1);
      onDegisti();
    } catch (e) {
      setHata(hataMesaji(e));
    } finally {
      setMesgul(false);
    }
  }

  return (
    <fieldset className="block">
      <legend className="text-[13px] text-metin-soluk">Fotoğraf</legend>
      <div className="mt-1 flex items-center gap-4">
        <AntrenorFoto id={antrenor.id} fotoVar={fotoVar} adSoyad={antrenor.ad_soyad} boyut="buyuk" surum={surum + yerelSurum} sinif="size-20 rounded-full text-2xl" />
        <div className="space-y-2">
          <input ref={dosyaGirdisi} type="file" accept="image/*" hidden data-testid="antrenor-foto-dosya" onChange={(e) => { fotoSec(e.target.files?.[0]); e.target.value = ""; }} />
          <div className="flex flex-wrap gap-2">
            <button type="button" className={dugme} disabled={mesgul || !onay} onClick={() => dosyaGirdisi.current?.click()}>
              {fotoVar ? "Değiştir" : "Fotoğraf ekle"}
            </button>
            {fotoVar && <button type="button" className={dugme} disabled={mesgul || !onay} onClick={() => void ayarla()}>Ayarla</button>}
            {fotoVar && <button type="button" className={dugme} disabled={mesgul} onClick={() => void kaldir()}>Sil</button>}
          </div>
        </div>
      </div>
      <label className="mt-3 flex items-start gap-3 min-h-11 cursor-pointer text-[13px]">
        <input type="checkbox" className="mt-0.5 size-4 shrink-0" checked={onay} onChange={(e) => setOnay(e.target.checked)} />
        <span>Antrenörün fotoğraf kullanımı için onayı alındı</span>
      </label>
      {hata && <p role="alert" className="text-[13px] text-hata mt-1">{hata}</p>}
      {kirpilacak && <FotoKirpma kaynak={kirpilacak} onKapat={() => setKirpilacak(null)} onTamam={kaydet} />}
    </fieldset>
  );
}

function Duzenle({ antrenor, surum, onFotoDegisti, onKapat, onKaydedildi }: { antrenor: AntrenorOzet; surum: number; onFotoDegisti: () => void; onKapat: () => void; onKaydedildi: () => void }) {
  // Giriş telefonsa alan ondan doldurulur (kartın telefonu ayrışmış olabilir); değilse (eski e-posta girişi) kartın telefonundan.
  const girisTelefonu = antrenor.giris && !antrenor.giris.includes("@") ? telefonSec(antrenor.giris, null) : null;
  const ilkTelefon = numaraCoz(telefonSec(antrenor.giris, antrenor.telefon));
  const [ad, setAd] = useState(antrenor.ad_soyad);
  const [telefon, setTelefon] = useState(ilkTelefon);
  const [gruplar, setGruplar] = useState<string[]>(antrenor.grup_idleri);
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);
  const girisEposta = antrenor.giris !== null && girisTelefonu === null;
  // Telefon yalnız değiştirildiyse ya da giriş telefon değilse (eski e-posta girişi) gönderilir.
  const telefonGonder = telefon !== ilkTelefon || girisEposta;
  const girisDegisecek = antrenor.giris !== null && telefonGonder && gecerliMi(telefon) && (girisEposta || apiyeCevir(telefon) !== girisTelefonu);
  const gruplarDegisti =
    gruplar.length !== antrenor.grup_idleri.length || gruplar.some((g) => !antrenor.grup_idleri.includes(g));

  async function gonder(e: FormEvent) {
    e.preventDefault();
    if (!ad.trim()) return setHata("Ad soyad zorunludur.");
    if (!telefon) return setHata("Telefon zorunludur.");
    if (!gecerliMi(telefon)) return setHata(TELEFON_HATA);
    setGonderiliyor(true);
    setHata(null);
    try {
      await antrenorGuncelle(antrenor.id, {
        ad_soyad: ad.trim(),
        ...(telefonGonder ? { telefon: apiyeCevir(telefon)! } : {}),
        ...(gruplarDegisti ? { grup_idleri: gruplar } : {}),
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
          <TelefonGirdisi value={telefon} onChange={setTelefon} />
          {girisDegisecek && (
            <span className="block mt-1 text-[12px] text-metin-soluk">
              {girisEposta
                ? `Bu antrenörün girişi e-posta (${antrenor.giris}); kaydedince giriş bu telefon olur.`
                : `Giriş numarası ${bicimle(girisTelefonu!)} → ${bicimle(apiyeCevir(telefon)!)} olarak değişir; açık oturumları kapanır.`}
            </span>
          )}
        </label>
        <FotoBolumu antrenor={antrenor} surum={surum} onDegisti={onFotoDegisti} />
        <GrupSecici secili={gruplar} onDegis={setGruplar} antrenorId={antrenor.id} />
        {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}
        <button type="submit" disabled={gonderiliyor} className={birincilDugme}>
          {gonderiliyor ? "Kaydediliyor…" : "Kaydet"}
        </button>
      </form>
    </Modal>
  );
}
