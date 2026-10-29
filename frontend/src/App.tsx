import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import { OnayProvider } from "./components/OnayPenceresi";
import { PANEL_YOLU } from "./lib/panel";
import YoneticiYerlesim from "./components/YoneticiYerlesim";
import AntrenorListe from "./pages/AntrenorListe";
import GrupDetay from "./pages/GrupDetay";
import GrupForm from "./pages/GrupForm";
import GrupListe from "./pages/GrupListe";
import Giris from "./pages/Giris";
import GelirRaporu from "./pages/GelirRaporu";
import GenelBakis from "./pages/GenelBakis";
import OgrenciDetay from "./pages/OgrenciDetay";
import OgrenciForm from "./pages/OgrenciForm";
import OgrenciListe from "./pages/OgrenciListe";
import SifreDegistir from "./pages/SifreDegistir";
import OdemeListe from "./pages/OdemeListe";
import PaketListe from "./pages/PaketListe";
import AntrenorYerlesim from "./components/AntrenorYerlesim";
import Takvim from "./pages/Takvim";
import VeliAna from "./pages/VeliAna";
import VeliCocuk from "./pages/VeliCocuk";
import VeliProfil from "./pages/VeliProfil";
import VeliYerlesim from "./components/VeliYerlesim";
import Yoklama from "./pages/Yoklama";

function KorumaliRota() {
  const { kullanici, yukleniyor } = useAuth();
  if (yukleniyor) return <div className="min-h-dvh grid place-items-center text-metin-soluk">Yükleniyor…</div>;
  if (!kullanici) return <Navigate to={PANEL_YOLU.veli} replace />;
  if (kullanici.sifre_degistirmeli) return <Navigate to="/sifre-degistir" replace />;
  if (kullanici.rol === "admin") return <Navigate to="/genel-bakis" replace />;
  if (kullanici.rol === "antrenor") return <Navigate to="/takvim" replace />;
  return <Navigate to="/panel" replace />;
}

function YoneticiRota() {
  const { kullanici, yukleniyor } = useAuth();
  if (yukleniyor) return <div className="min-h-dvh grid place-items-center text-metin-soluk">Yükleniyor…</div>;
  if (!kullanici) return <Navigate to={PANEL_YOLU.yonetici} replace />;
  if (kullanici.sifre_degistirmeli) return <Navigate to="/sifre-degistir" replace />;
  if (kullanici.rol !== "admin") return <Navigate to="/" replace />;
  return <YoneticiYerlesim />;
}

function VeliRota() {
  const { kullanici, yukleniyor } = useAuth();
  if (yukleniyor) return <div className="min-h-dvh grid place-items-center text-metin-soluk">Yükleniyor…</div>;
  if (!kullanici) return <Navigate to={PANEL_YOLU.veli} replace />;
  if (kullanici.sifre_degistirmeli) return <Navigate to="/sifre-degistir" replace />;
  if (kullanici.rol !== "veli" && kullanici.rol !== "ogrenci") return <Navigate to="/" replace />;
  return <VeliYerlesim />;
}

// Takvim ve yoklama ekranlarını yönetici ve antrenör kullanır; her biri kendi yerleşimini görür.
function TakvimRota() {
  const { kullanici, yukleniyor } = useAuth();
  if (yukleniyor) return <div className="min-h-dvh grid place-items-center text-metin-soluk">Yükleniyor…</div>;
  if (!kullanici) return <Navigate to={PANEL_YOLU.antrenor} replace />;
  if (kullanici.sifre_degistirmeli) return <Navigate to="/sifre-degistir" replace />;
  if (kullanici.rol === "admin") return <YoneticiYerlesim />;
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
          <Route path="/sifre-degistir" element={<SifreDegistir />} />
          <Route path="/" element={<KorumaliRota />} />
          <Route element={<TakvimRota />}>
            <Route path="/takvim" element={<Takvim />} />
            <Route path="/oturum/:id" element={<Yoklama />} />
          </Route>
          <Route element={<VeliRota />}>
            <Route path="/panel" element={<VeliAna />} />
            <Route path="/panel/cocuk/:id" element={<VeliCocuk />} />
            <Route path="/profil" element={<VeliProfil />} />
          </Route>
          <Route element={<YoneticiRota />}>
            <Route path="/genel-bakis" element={<GenelBakis />} />
            <Route path="/ogrenciler" element={<OgrenciListe />} />
            <Route path="/ogrenciler/yeni" element={<OgrenciForm />} />
            <Route path="/ogrenciler/:id" element={<OgrenciDetay />} />
            <Route path="/ogrenciler/:id/duzenle" element={<OgrenciForm />} />
            <Route path="/antrenorler" element={<AntrenorListe />} />
            <Route path="/odemeler" element={<OdemeListe />} />
            <Route path="/gelir-raporu" element={<GelirRaporu />} />
            <Route path="/paketler" element={<PaketListe />} />
            <Route path="/gruplar" element={<GrupListe />} />
            <Route path="/gruplar/yeni" element={<GrupForm />} />
            <Route path="/gruplar/:id" element={<GrupDetay />} />
            <Route path="/gruplar/:id/duzenle" element={<GrupForm />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </OnayProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
