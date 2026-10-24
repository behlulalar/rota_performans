import { useAuth, type Rol } from "../auth/AuthProvider";

const ROL_ADI: Record<Rol, string> = {
  admin: "Yönetici",
  antrenor: "Antrenör",
  veli: "Veli",
  ogrenci: "Öğrenci",
};

// Yer tutucu: rol bazlı paneller Faz 1–3'te bu sayfanın yerini alacak.
export default function Panel() {
  const { kullanici, cikisYap } = useAuth();
  if (!kullanici) return null;

  return (
    <main className="min-h-dvh px-4 py-8 max-w-3xl mx-auto">
      <header className="flex items-center justify-between mb-8">
        <div>
          <div className="text-altin text-xs tracking-[0.3em] uppercase">Rota Performans</div>
          <h1 className="text-xl font-semibold">Hoş geldiniz</h1>
        </div>
        <button
          onClick={() => void cikisYap()}
          className="rounded-lg border border-cizgi px-3 py-1.5 text-sm text-metin-soluk hover:border-altin hover:text-metin transition-colors"
        >
          Çıkış yap
        </button>
      </header>

      <section className="bg-yuzey border border-cizgi rounded-2xl p-6">
        <p className="text-metin-soluk text-sm">Oturum açan hesap</p>
        <p className="mt-1 font-medium">{kullanici.giris}</p>
        <p className="mt-3 inline-block rounded-full bg-yuzey-yuksek border border-cizgi px-3 py-1 text-xs text-altin">
          {ROL_ADI[kullanici.rol]}
        </p>
      </section>

      {(kullanici.rol === "veli" || kullanici.rol === "ogrenci") && (
        <p className="mt-4 text-sm text-metin-soluk">Veli paneli yakında burada olacak.</p>
      )}
    </main>
  );
}
