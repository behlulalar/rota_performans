import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { antrenorleriGetir, type AntrenorOzet } from "../api/antrenor";
import { oturumlariUret, takvimGetir, type OturumOzet } from "../api/takvim";
import { hataMesaji } from "../lib/dogrulama";
import { GUNLER, saat } from "../lib/program";
import { bugun, gunEkle, haftaBasi, kisaTarih, yyyyAyGun } from "../lib/tarih";
import SayfaBasligi from "../components/SayfaBasligi";
import { basariKutusu, dugme, rozetBasari, rozetNotr, rozetUyari, secimKutusu } from "../lib/stil";


function OturumKarti({ o, bugunStr }: { o: OturumOzet; bugunStr: string }) {
  const iptal = o.durum === "iptal";
  const bekliyor = !iptal && !o.yoklama_alindi && o.tarih <= bugunStr;
  return (
    <Link
      to={`/oturum/${o.id}`}
      className={`block rounded-[10px] border border-cizgi bg-yuzey-yuksek px-3 py-2.5 hover:border-altin transition-colors ${iptal ? "opacity-50" : ""}`}
    >
      <div className="num text-[13px] font-semibold">
        {saat(o.baslangic)}–{saat(o.bitis)}
      </div>
      <div className={`mt-0.5 text-sm ${iptal ? "line-through" : ""}`}>{o.grup.ad}</div>
      <div className="num mt-1 text-xs text-metin-soluk">
        {o.ogrenci_sayisi} öğrenci{o.antrenor ? ` · ${o.antrenor.ad_soyad}` : ""}
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {iptal && <span className={rozetNotr}>İptal</span>}
        {!iptal && o.yoklama_alindi && <span className={rozetBasari}>Yoklama alındı</span>}
        {bekliyor && <span className={rozetUyari}>Yoklama bekliyor</span>}
      </div>
    </Link>
  );
}

export default function Takvim() {
  const { kullanici } = useAuth();
  const admin = kullanici?.rol === "admin";
  const bugunStr = bugun();
  const [hafta, setHafta] = useState(() => haftaBasi(new Date()));
  const [antrenorler, setAntrenorler] = useState<AntrenorOzet[]>([]);
  const [antrenorId, setAntrenorId] = useState("");
  const [oturumlar, setOturumlar] = useState<OturumOzet[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [bilgi, setBilgi] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const [yenile, setYenile] = useState(0);
  const [kapali, setKapali] = useState<Set<string>>(new Set());

  const gunler = useMemo(() => Array.from({ length: 7 }, (_, i) => gunEkle(hafta, i)), [hafta]);
  const bas = yyyyAyGun(gunler[0]);
  const bit = yyyyAyGun(gunler[6]);

  useEffect(() => {
    if (!admin) return;
    antrenorleriGetir(true).then(setAntrenorler).catch(() => setAntrenorler([]));
  }, [admin]);

  useEffect(() => {
    let iptal = false;
    setOturumlar(null);
    setHata(null);
    takvimGetir(bas, bit, admin && antrenorId ? antrenorId : undefined)
      .then((v) => !iptal && setOturumlar(v))
      .catch((e) => !iptal && setHata(hataMesaji(e)));
    return () => {
      iptal = true;
    };
  }, [bas, bit, admin, antrenorId, yenile]);

  // Mobilde yalnızca bugün açık gelir (görünen hafta bugünü içermiyorsa tüm günler açık).
  useEffect(() => {
    const icerir = gunler.some((g) => yyyyAyGun(g) === bugunStr);
    setKapali(new Set(icerir ? gunler.map(yyyyAyGun).filter((g) => g !== bugunStr) : []));
  }, [gunler, bugunStr]);

  const uret = async () => {
    setMesgul(true);
    setHata(null);
    setBilgi(null);
    try {
      const y = await oturumlariUret(bas, bit);
      setBilgi(`${y.olusturulan} ders oluşturuldu`);
      setYenile((n) => n + 1);
    } catch (e) {
      setHata(hataMesaji(e));
    } finally {
      setMesgul(false);
    }
  };

  const gunToggle = (g: string) =>
    setKapali((k) => {
      const yeni = new Set(k);
      if (yeni.has(g)) yeni.delete(g);
      else yeni.add(g);
      return yeni;
    });

  const bugunHaftada = bas <= bugunStr && bugunStr <= bit;

  return (
    <div className="space-y-4">
      <SayfaBasligi
        baslik="Takvim"
        aciklama={
          oturumlar
            ? `${kisaTarih(gunler[0])} – ${kisaTarih(gunler[6])} haftası · ${oturumlar.filter((o) => o.durum !== "iptal").length} ders`
            : "Haftalık ders programı ve yoklama durumu"
        }
        eylemler={
          admin ? (
            <>
              <select
                aria-label="Antrenör filtresi"
                value={antrenorId}
                onChange={(e) => setAntrenorId(e.target.value)}
                className={secimKutusu}
              >
                <option value="">Tüm antrenörler</option>
                {antrenorler.map((a) => (
                  <option key={a.id} value={a.id}>{a.ad_soyad}</option>
                ))}
              </select>
              <button className={dugme} disabled={mesgul} onClick={() => void uret()}>
                Oturumları üret
              </button>
            </>
          ) : undefined
        }
      />

      <div className="flex items-center gap-2">
        <button className={dugme} aria-label="Önceki hafta" onClick={() => setHafta((h) => gunEkle(h, -7))}>←</button>
        <div className="num flex-1 text-center text-[13px] font-medium">
          {kisaTarih(gunler[0])} – {kisaTarih(gunler[6])}
        </div>
        <button className={dugme} aria-label="Sonraki hafta" onClick={() => setHafta((h) => gunEkle(h, 7))}>→</button>
        <button className={dugme} disabled={bugunHaftada} onClick={() => setHafta(haftaBasi(new Date()))}>Bugün</button>
      </div>

      {bilgi && <p role="status" className={basariKutusu}>{bilgi}</p>}
      {hata && <p role="alert" className="text-[13px] text-hata">{hata}</p>}

      {oturumlar === null && !hata && <p className="text-metin-soluk py-10 text-center">Yükleniyor…</p>}

      {oturumlar !== null && oturumlar.length === 0 && (
        <p className="rounded-[14px] border border-cizgi bg-yuzey px-4 py-6 text-sm text-metin-soluk text-center">
          {admin
            ? "Bu hafta için ders oturumu yok. Oturumları üret butonuyla grup programlarından oluşturabilirsiniz."
            : "Bu hafta için ders oturumu yok."}
        </p>
      )}

      {oturumlar !== null && oturumlar.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 min-[1360px]:grid-cols-7 gap-2 items-start">
          {gunler.map((g, i) => {
            const s = yyyyAyGun(g);
            const liste = oturumlar
              .filter((o) => o.tarih === s)
              .sort((a, b) => a.baslangic.localeCompare(b.baslangic));
            const acik = !kapali.has(s);
            const buGun = s === bugunStr;
            return (
              <section key={s} aria-label={`${GUNLER[i]} ${kisaTarih(g)}`} className="min-w-0">
                <button
                  type="button"
                  onClick={() => gunToggle(s)}
                  aria-expanded={acik}
                  aria-current={buGun ? "date" : undefined}
                  className={`md:cursor-default w-full flex items-center gap-3 rounded-[10px] px-3 py-2 min-h-14 text-left border ${
                    buGun
                      ? "border-2 border-altin bg-altin/15 text-altin-metin"
                      : "border-cizgi bg-yuzey text-metin"
                  }`}
                >
                  <span className="num font-display text-[32px] leading-none w-11 text-center shrink-0">{g.getDate()}</span>
                  <span className="flex-1 min-w-0 leading-tight">
                    <span className="block text-[15px] font-semibold">{GUNLER[i]}</span>
                    <span className={`block text-[13px] ${buGun ? "" : "text-metin-orta"}`}>
                      {g.toLocaleDateString("tr-TR", { month: "long" })}
                    </span>
                  </span>
                  {buGun && (
                    <span className="rounded-full bg-altin text-[#111] text-[10px] font-semibold uppercase tracking-[0.12em] px-2 py-0.5">Bugün</span>
                  )}
                  <span className="num md:hidden text-xs text-metin-soluk">{liste.length} ders {acik ? "▲" : "▼"}</span>
                </button>
                <div className={`${acik ? "block" : "hidden"} md:block mt-2 space-y-2`}>
                  {liste.length === 0 ? (
                    <p className="text-xs text-metin-soluk px-1">Ders yok</p>
                  ) : (
                    liste.map((o) => <OturumKarti key={o.id} o={o} bugunStr={bugunStr} />)
                  )}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
