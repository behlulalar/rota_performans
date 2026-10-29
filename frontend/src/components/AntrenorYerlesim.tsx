import { ANTRENOR_MENUSU } from "../lib/menu";
import Kabuk from "./Kabuk";

export default function AntrenorYerlesim() {
  return <Kabuk menu={ANTRENOR_MENUSU} sekmeler={ANTRENOR_MENUSU[0].ogeler} yerlesim="ust" />;
}
