import { useAuth } from "../auth/AuthProvider";
import { DESTEK_MENUSU, YONETICI_MENUSU, YONETICI_SEKMELERI } from "../lib/menu";
import Kabuk from "./Kabuk";

export default function YoneticiYerlesim() {
  const { kullanici } = useAuth();
  return (
    <Kabuk
      menu={kullanici?.rol === "destek" ? DESTEK_MENUSU : YONETICI_MENUSU}
      sekmeler={YONETICI_SEKMELERI}
      arkaPlan
    />
  );
}
