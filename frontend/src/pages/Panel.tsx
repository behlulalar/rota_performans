import { useAuth, type Rol } from "../auth/AuthProvider";
import Kart from "../components/Kart";
import TemaDugmesi from "../components/TemaDugmesi";
import { rozetBirincil } from "../lib/stil";

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
    <div className="min-h-dvh">
      <header className="h-14 bg-serit text-white flex items-center gap-3 px-4">
        <span
          aria-hidden="true"
          className="size-8 rounded-[3px] border border-serit-ikon-secili/50 grid place-items-center text-serit-ikon-secili text-[11px] font-semibold tracking-wider"
        >
          RP
        </span>
        <span className="flex-1 font-display font-medium text-[19px]">Rota Performans</span>
        <TemaDugmesi gorunum="serit" />
        <button
          onClick={() => void cikisYap()}
          className="rounded-[3px] border border-serit-ikon/50 px-3 min-h-11 text-[13px] text-white hover:border-serit-ikon-secili transition-colors"
        >
          Çıkış yap
        </button>
      </header>

      <main className="px-4 py-6 max-w-3xl mx-auto">
        <div className="mb-7">
          <div className="eyebrow">Panel</div>
          <h1 className="mt-1.5 font-display font-medium text-[28px] md:text-[38px] leading-[1.1]">Hoş geldiniz</h1>
          <p className="mt-2 text-[15px] text-metin-soluk">Hesabınızla oturum açıldı: {ROL_ADI[kullanici.rol]}</p>
        </div>

        <Kart baslik="Oturum açan hesap">
          <p className="font-medium">{kullanici.giris}</p>
          <p className="mt-3">
            <span className={rozetBirincil}>{ROL_ADI[kullanici.rol]}</span>
          </p>
        </Kart>

        {(kullanici.rol === "veli" || kullanici.rol === "ogrenci") && (
          <p className="mt-4 text-sm text-metin-soluk">Veli paneli yakında burada olacak.</p>
        )}
      </main>
    </div>
  );
}
