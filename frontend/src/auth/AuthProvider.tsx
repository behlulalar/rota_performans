import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, belirteciAyarla, oturumuYenile } from "../lib/api";

export type Rol = "admin" | "antrenor" | "veli" | "ogrenci";
export type Kullanici = { id: string; rol: Rol; giris: string };

type AuthDegeri = {
  kullanici: Kullanici | null;
  yukleniyor: boolean;
  girisYap: (giris: string, sifre: string) => Promise<void>;
  cikisYap: () => Promise<void>;
};

const AuthBaglami = createContext<AuthDegeri | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [kullanici, setKullanici] = useState<Kullanici | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);

  // Sayfa açılışında yenileme çerezi varsa oturumu sessizce geri getirir.
  useEffect(() => {
    let iptal = false;
    (async () => {
      try {
        if (await oturumuYenile()) {
          const ben = await api<Kullanici>("/api/auth/me");
          if (!iptal) setKullanici(ben);
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

  const girisYap = useCallback(async (giris: string, sifre: string) => {
    const yanit = await api<{ access_token: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ giris, sifre }),
    });
    belirteciAyarla(yanit.access_token);
    setKullanici(await api<Kullanici>("/api/auth/me"));
  }, []);

  const cikisYap = useCallback(async () => {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } finally {
      belirteciAyarla(null);
      setKullanici(null);
    }
  }, []);

  const deger = useMemo(
    () => ({ kullanici, yukleniyor, girisYap, cikisYap }),
    [kullanici, yukleniyor, girisYap, cikisYap],
  );
  return <AuthBaglami.Provider value={deger}>{children}</AuthBaglami.Provider>;
}

export function useAuth(): AuthDegeri {
  const deger = useContext(AuthBaglami);
  if (!deger) throw new Error("useAuth, AuthProvider içinde kullanılmalı");
  return deger;
}
