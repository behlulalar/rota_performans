import { useRef } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth, type Rol } from "./auth/AuthProvider";
import { OnayProvider } from "./components/OnayPenceresi";
import { PANEL_YOLU } from "./lib/panel";
import YoneticiYerlesim from "./components/YoneticiYerlesim";
import AntrenorListe from "./pages/AntrenorListe";
import YoneticiListe from "./pages/YoneticiListe";
import GrupDetay from "./pages/GrupDetay";
import GrupForm from "./pages/GrupForm";
import GrupListe from "./pages/GrupListe";
import Giris from "./pages/Giris";
import DestekGiris from "./pages/DestekGiris";
import DestekSistemDurumu from "./pages/DestekSistemDurumu";
import DestekHesaplar from "./pages/DestekHesaplar";
import DestekBildirimler from "./pages/DestekBildirimler";
import GelirRaporu from "./pages/GelirRaporu";
import BildirimYonetimi from "./pages/BildirimYonetimi";
import DuyuruDetay from "./pages/DuyuruDetay";
import DuyuruForm from "./pages/DuyuruForm";
import Duyurular from "./pages/Duyurular";
import DenetimKaydi from "./pages/DenetimKaydi";
import Ayarlar from "./pages/Ayarlar";
import GenelBakis from "./pages/GenelBakis";
import OgrenciDetay from "./pages/OgrenciDetay";
import OgrenciForm from "./pages/OgrenciForm";
import OgrenciListe from "./pages/OgrenciListe";
import SifreDegistir from "./pages/SifreDegistir";
import OdemeListe from "./pages/OdemeListe";
import PaketListe from "./pages/PaketListe";
import AntrenorBugun from "./pages/AntrenorBugun";
import AntrenorProfil from "./pages/AntrenorProfil";
import AntrenorYerlesim from "./components/AntrenorYerlesim";
import Takvim from "./pages/Takvim";
import VeliAna from "./pages/VeliAna";
import VeliCocuk from "./pages/VeliCocuk";
import VeliProfil from "./pages/VeliProfil";
import VeliIletisim from "./pages/VeliIletisim";
import VeliYerlesim from "./components/VeliYerlesim";
import Yoklama from "./pages/Yoklama";

function KorumaliRota() {
  const { kullanici, yukleniyor } = useAuth();
  if (yukleniyor) return <div className="min-h-[calc(100dvh/var(--olcek,1))] grid place-items-center text-metin-soluk">Yükleniyor…</div>;
  if (!kullanici) return <Navigate to={PANEL_YOLU.veli} replace />;
  if (kullanici.sifre_degistirmeli) return <Navigate to="/sifre-degistir" replace />;
  if (kullanici.rol === "admin" || kullanici.rol === "destek") return <Navigate to="/genel-bakis" replace />;
  if (kullanici.rol === "antrenor") return <Navigate to="/bugun" replace />;
  return <Navigate to="/panel" replace />;
}

// Yönetici ekranlarını yönetici ve teknik destek kullanır. Oturum düşerse destek kendi giriş sayfasına döner.
function YoneticiRota() {
  const { kullanici, yukleniyor } = useAuth();
  const { pathname } = useLocation();
  const sonRol = useRef<Rol | null>(null);
  if (kullanici) sonRol.current = kullanici.rol;
  if (yukleniyor) return <div className="min-h-[calc(100dvh/var(--olcek,1))] grid place-items-center text-metin-soluk">Yükleniyor…</div>;
  if (!kullanici) {
    const destek = sonRol.current === "destek" || pathname.startsWith("/destek/");
    return <Navigate to={destek ? PANEL_YOLU.destek : PANEL_YOLU.yonetici} replace />;
  }
  if (kullanici.sifre_degistirmeli) return <Navigate to="/sifre-degistir" replace />;
  if (kullanici.rol !== "admin" && kullanici.rol !== "destek") return <Navigate to="/" replace />;
  return <YoneticiYerlesim />;
}

// Teknik destek ekranları yalnız destek rolüne açıktır; yönetici genel bakışa döner.
function DestekRota() {
  const { kullanici } = useAuth();
  if (kullanici?.rol !== "destek") return <Navigate to="/genel-bakis" replace />;
  return <Outlet />;
}

function VeliRota() {
  const { kullanici, yukleniyor } = useAuth();
  if (yukleniyor) return <div className="min-h-[calc(100dvh/var(--olcek,1))] grid place-items-center text-metin-soluk">Yükleniyor…</div>;
  if (!kullanici) return <Navigate to={PANEL_YOLU.veli} replace />;
  if (kullanici.sifre_degistirmeli) return <Navigate to="/sifre-degistir" replace />;
  if (kullanici.rol !== "veli" && kullanici.rol !== "ogrenci") return <Navigate to="/" replace />;
  return <VeliYerlesim />;
}

// Bugün ve Profilim yalnız antrenöre aittir; yönetici kendi ekranlarına döner.
function AntrenorRota() {
  const { kullanici, yukleniyor } = useAuth();
  if (yukleniyor) return <div className="min-h-[calc(100dvh/var(--olcek,1))] grid place-items-center text-metin-soluk">Yükleniyor…</div>;
  if (!kullanici) return <Navigate to={PANEL_YOLU.antrenor} replace />;
  if (kullanici.sifre_degistirmeli) return <Navigate to="/sifre-degistir" replace />;
  if (kullanici.rol !== "antrenor") return <Navigate to="/" replace />;
  return <AntrenorYerlesim />;
}

// Takvim ve yoklama ekranlarını yönetici ve antrenör kullanır; her biri kendi yerleşimini görür.
function TakvimRota() {
  const { kullanici, yukleniyor } = useAuth();
  if (yukleniyor) return <div className="min-h-[calc(100dvh/var(--olcek,1))] grid place-items-center text-metin-soluk">Yükleniyor…</div>;
  if (!kullanici) return <Navigate to={PANEL_YOLU.antrenor} replace />;
  if (kullanici.sifre_degistirmeli) return <Navigate to="/sifre-degistir" replace />;
  if (kullanici.rol === "admin" || kullanici.rol === "destek") return <YoneticiYerlesim />;
  if (kullanici.rol === "antrenor") return <AntrenorYerlesim />;
  return <Navigate to="/" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <OnayProvider>
        <Routes>
          <Route path="/giris" element={<Giris panel="veli" />} />
          <Route path="/antrenor-giris" element={<Giris panel="antrenor" />} />
          <Route path="/yonetici-giris" element={<Giris panel="yonetici" />} />
          <Route path="/destek-giris" element={<DestekGiris />} />
          <Route path="/sifre-degistir" element={<SifreDegistir />} />
          <Route path="/" element={<KorumaliRota />} />
          <Route element={<AntrenorRota />}>
            <Route path="/bugun" element={<AntrenorBugun />} />
            <Route path="/profilim" element={<AntrenorProfil />} />
          </Route>
          <Route element={<TakvimRota />}>
            <Route path="/takvim" element={<Takvim />} />
            <Route path="/oturum/:id" element={<Yoklama />} />
          </Route>
          <Route element={<VeliRota />}>
            <Route path="/panel" element={<VeliAna />} />
            <Route path="/panel/cocuk/:id" element={<VeliCocuk />} />
            <Route path="/profil" element={<VeliProfil />} />
            <Route path="/iletisim" element={<VeliIletisim />} />
          </Route>
          <Route element={<YoneticiRota />}>
            <Route path="/genel-bakis" element={<GenelBakis />} />
            <Route path="/ogrenciler" element={<OgrenciListe />} />
            <Route path="/ogrenciler/yeni" element={<OgrenciForm />} />
            <Route path="/ogrenciler/:id" element={<OgrenciDetay />} />
            <Route path="/ogrenciler/:id/duzenle" element={<OgrenciForm />} />
            <Route path="/antrenorler" element={<AntrenorListe />} />
            <Route path="/yoneticiler" element={<YoneticiListe />} />
            <Route path="/odemeler" element={<OdemeListe />} />
            <Route path="/gelir-raporu" element={<GelirRaporu />} />
            <Route path="/duyurular" element={<Duyurular />} />
            <Route path="/duyurular/yeni" element={<DuyuruForm />} />
            <Route path="/duyurular/:id" element={<DuyuruDetay />} />
            <Route path="/bildirimler" element={<BildirimYonetimi />} />
            <Route path="/ayarlar" element={<Ayarlar />} />
            <Route path="/paketler" element={<PaketListe />} />
            <Route path="/gruplar" element={<GrupListe />} />
            <Route path="/gruplar/yeni" element={<GrupForm />} />
            <Route path="/gruplar/:id" element={<GrupDetay />} />
            <Route path="/gruplar/:id/duzenle" element={<GrupForm />} />
            <Route element={<DestekRota />}>
              <Route path="/destek/sistem-durumu" element={<DestekSistemDurumu />} />
              <Route path="/destek/hesaplar" element={<DestekHesaplar />} />
              <Route path="/destek/bildirimler" element={<DestekBildirimler />} />
              <Route path="/destek/denetim-kaydi" element={<DenetimKaydi />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </OnayProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
