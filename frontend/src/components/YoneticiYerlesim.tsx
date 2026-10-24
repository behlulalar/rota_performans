import { YONETICI_MENUSU, YONETICI_SEKMELERI } from "../lib/menu";
import Kabuk from "./Kabuk";

export default function YoneticiYerlesim() {
  return <Kabuk menu={YONETICI_MENUSU} sekmeler={YONETICI_SEKMELERI} />;
}
