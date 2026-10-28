import { VELI_MENUSU } from "../lib/menu";
import Kabuk from "./Kabuk";

export default function VeliYerlesim() {
  return <Kabuk menu={VELI_MENUSU} sekmeler={VELI_MENUSU[0].ogeler} yerlesim="ust" />;
}
