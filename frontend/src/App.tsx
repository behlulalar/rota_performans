import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import YoneticiYerlesim from "./components/YoneticiYerlesim";
import Giris from "./pages/Giris";
import GenelBakis from "./pages/GenelBakis";
import OgrenciDetay from "./pages/OgrenciDetay";
import OgrenciForm from "./pages/OgrenciForm";
import OgrenciListe from "./pages/OgrenciListe";
import Panel from "./pages/Panel";

function KorumaliRota() {
  const { kullanici, yukleniyor } = useAuth();
  if (yukleniyor) return <div className="min-h-dvh grid place-items-center text-metin-soluk">Yükleniyor…</div>;
  if (!kullanici) return <Navigate to="/giris" replace />;
  return kullanici.rol === "admin" ? <Navigate to="/ogrenciler" replace /> : <Panel />;
}

function YoneticiRota() {
  const { kullanici, yukleniyor } = useAuth();
  if (yukleniyor) return <div className="min-h-dvh grid place-items-center text-metin-soluk">Yükleniyor…</div>;
  if (!kullanici) return <Navigate to="/giris" replace />;
  if (kullanici.rol !== "admin") return <Navigate to="/" replace />;
  return <YoneticiYerlesim />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/giris" element={<Giris />} />
          <Route path="/" element={<KorumaliRota />} />
          <Route element={<YoneticiRota />}>
            <Route path="/genel-bakis" element={<GenelBakis />} />
            <Route path="/ogrenciler" element={<OgrenciListe />} />
            <Route path="/ogrenciler/yeni" element={<OgrenciForm />} />
            <Route path="/ogrenciler/:id" element={<OgrenciDetay />} />
            <Route path="/ogrenciler/:id/duzenle" element={<OgrenciForm />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
