import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, belirteciAyarla, oturumuYenile, sifreZorunluDinleyiciAyarla } from "../lib/api";
import type { Panel } from "../lib/panel";
import { useBostaKapanma } from "../lib/bosta";
import { cikisIsaretle, cikisYapildiMi, hatirlananiKaydet, hatirlananiOku, hatirlananiSil } from "../lib/hatirla";

export type Rol = "admin" | "destek" | "antrenor" | "veli" | "ogrenci";
export type Kullanici = { id: string; rol: Rol; giris: string; ad_soyad: string | null; sifre_degistirmeli: boolean; telefon?: string | null };

/** Teknik destek şifreyle girince oturum açılmaz; ikinci adım (kurulum ya da doğrulama) için bekleyen belirteç döner. */
export type IkiAdim = { durum: "kurulum" | "dogrulama"; bekleyen_belirtec: string; expires_in: number };

type AuthDegeri = {
  kullanici: Kullanici | null;
  yukleniyor: boolean;
  /** Hatırlanan kullanıcı varken sessiz yenileme başarısız olduysa (oturum süresi dolmuş) true. */
  oturumSuresiDoldu: boolean;
  /** Boşta kalma süresi dolduğu için oturum kapatıldıysa true; yeni girişte sıfırlanır. */
  bostaKapandi: boolean;
  /** Destek hesabında oturum açmaz, ikinci adımı döner; diğer rollerde oturum açar ve null döner. */
  girisYap: (giris: string, sifre: string, beniHatirla: boolean, panel: Panel) => Promise<IkiAdim | null>;
  /** İkinci adım bittikten sonra elde edilen erişim belirteciyle oturumu açar. */
  belirtecleGiris: (erisimBelirteci: string, beniHatirla: boolean, panel: Panel) => Promise<void>;
  cikisYap: () => Promise<void>;
  /** Zorunlu şifre değişiminden sonra çağrılır; kullanıcı durumunu sunucudan yeniler. */
  sifreDegistirildi: () => Promise<void>;
};

const AuthBaglami = createContext<AuthDegeri | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [kullanici, setKullanici] = useState<Kullanici | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [oturumSuresiDoldu, setOturumSuresiDoldu] = useState(false);
  const [bostaKapandi, setBostaKapandi] = useState(false);

  // Sayfa açılışında yenileme çerezi varsa oturumu sessizce geri getirir.
  useEffect(() => {
    let iptal = false;
    (async () => {
      try {
        if (await oturumuYenile()) {
          const ben = await api<Kullanici>("/api/auth/me");
          if (!iptal) setKullanici(ben);
        } else if (!iptal && hatirlananiOku() && !cikisYapildiMi()) {
          setOturumSuresiDoldu(true);
        }
      } catch {
        /* oturum yok */
      } finally {
        if (!iptal) setYukleniyor(false);
      }
    })();
    return () => {
      iptal = true;
    };
  }, []);

  const girisYap = useCallback(async (giris: string, sifre: string, beniHatirla: boolean, panel: Panel) => {
    const yanit = await api<{ access_token?: string; iki_adim?: boolean } & Partial<IkiAdim>>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ giris, sifre, beni_hatirla: beniHatirla, panel }),
    });
    if (yanit.iki_adim && yanit.durum && yanit.bekleyen_belirtec) {
      return { durum: yanit.durum, bekleyen_belirtec: yanit.bekleyen_belirtec, expires_in: yanit.expires_in ?? 300 };
    }
    belirteciAyarla(yanit.access_token ?? null);
    const ben = await api<Kullanici>("/api/auth/me");
    if (beniHatirla) hatirlananiKaydet({ giris: ben.giris, ad: ben.ad_soyad || ben.giris, panel });
    else hatirlananiSil();
    cikisIsaretle(false);
    setOturumSuresiDoldu(false);
    setBostaKapandi(false);
    setKullanici(ben);
    return null;
  }, []);

  const belirtecleGiris = useCallback(async (erisimBelirteci: string, beniHatirla: boolean, panel: Panel) => {
    belirteciAyarla(erisimBelirteci);
    const ben = await api<Kullanici>("/api/auth/me");
    if (beniHatirla) hatirlananiKaydet({ giris: ben.giris, ad: ben.ad_soyad || ben.giris, panel });
    else hatirlananiSil();
    cikisIsaretle(false);
    setOturumSuresiDoldu(false);
    setBostaKapandi(false);
    setKullanici(ben);
  }, []);

  const cikisYap = useCallback(async () => {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } finally {
      belirteciAyarla(null);
      cikisIsaretle(true);
      setOturumSuresiDoldu(false);
      setKullanici(null);
    }
  }, []);

  // Hareketsizlik: BOSTA_DAKIKA boyunca fare/klavye/dokunma yoksa oturum sunucuda ve burada kapanır.
  const bostaKapat = useCallback(() => {
    fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" }).catch(() => {});
    belirteciAyarla(null);
    cikisIsaretle(false);
    setOturumSuresiDoldu(false);
    setBostaKapandi(true);
    setKullanici(null);
  }, []);
  useBostaKapanma(kullanici !== null, bostaKapat);

  const sifreDegistirildi = useCallback(async () => {
    try {
      const ben = await api<Kullanici>("/api/auth/me");
      setKullanici(ben);
    } catch {
      setKullanici((k) => (k ? { ...k, sifre_degistirmeli: false } : k));
    }
  }, []);

  // Nadir yarış: sunucu 403 sifre_degistirmeli derse durumu yenile; yönlendirmeyi rota koruması yapar.
  useEffect(() => {
    sifreZorunluDinleyiciAyarla(() => {
      api<Kullanici>("/api/auth/me").then(setKullanici, () => {});
    });
    return () => sifreZorunluDinleyiciAyarla(null);
  }, []);

  const deger = useMemo(
    () => ({ kullanici, yukleniyor, oturumSuresiDoldu, bostaKapandi, girisYap, belirtecleGiris, cikisYap, sifreDegistirildi }),
    [kullanici, yukleniyor, oturumSuresiDoldu, bostaKapandi, girisYap, belirtecleGiris, cikisYap, sifreDegistirildi],
  );
  return <AuthBaglami.Provider value={deger}>{children}</AuthBaglami.Provider>;
}

export function useAuth(): AuthDegeri {
  const deger = useContext(AuthBaglami);
  if (!deger) throw new Error("useAuth, AuthProvider içinde kullanılmalı");
  return deger;
}
