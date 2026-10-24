import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, belirteciAyarla, oturumuYenile } from "../lib/api";
import { cikisIsaretle, cikisYapildiMi, hatirlananiKaydet, hatirlananiOku, hatirlananiSil } from "../lib/hatirla";

export type Rol = "admin" | "antrenor" | "veli" | "ogrenci";
export type Kullanici = { id: string; rol: Rol; giris: string; ad_soyad: string | null };

type AuthDegeri = {
  kullanici: Kullanici | null;
  yukleniyor: boolean;
  /** Hatırlanan kullanıcı varken sessiz yenileme başarısız olduysa (oturum süresi dolmuş) true. */
  oturumSuresiDoldu: boolean;
  girisYap: (giris: string, sifre: string, beniHatirla: boolean) => Promise<void>;
  cikisYap: () => Promise<void>;
};

const AuthBaglami = createContext<AuthDegeri | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [kullanici, setKullanici] = useState<Kullanici | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [oturumSuresiDoldu, setOturumSuresiDoldu] = useState(false);

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

  const girisYap = useCallback(async (giris: string, sifre: string, beniHatirla: boolean) => {
    const yanit = await api<{ access_token: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ giris, sifre, beni_hatirla: beniHatirla }),
    });
    belirteciAyarla(yanit.access_token);
    const ben = await api<Kullanici>("/api/auth/me");
    if (beniHatirla) hatirlananiKaydet({ giris: ben.giris, ad: ben.ad_soyad || ben.giris });
    else hatirlananiSil();
    cikisIsaretle(false);
    setOturumSuresiDoldu(false);
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

  const deger = useMemo(
    () => ({ kullanici, yukleniyor, oturumSuresiDoldu, girisYap, cikisYap }),
    [kullanici, yukleniyor, oturumSuresiDoldu, girisYap, cikisYap],
  );
  return <AuthBaglami.Provider value={deger}>{children}</AuthBaglami.Provider>;
}

export function useAuth(): AuthDegeri {
  const deger = useContext(AuthBaglami);
  if (!deger) throw new Error("useAuth, AuthProvider içinde kullanılmalı");
  return deger;
}
