import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import Giris from "./pages/Giris";
import Panel from "./pages/Panel";

function KorumaliRota() {
  const { kullanici, yukleniyor } = useAuth();
  if (yukleniyor) return <div className="min-h-dvh grid place-items-center text-metin-soluk">Yükleniyor…</div>;
  return kullanici ? <Panel /> : <Navigate to="/giris" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/giris" element={<Giris />} />
          <Route path="/" element={<KorumaliRota />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
