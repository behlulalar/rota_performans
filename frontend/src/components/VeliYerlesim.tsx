import { VELI_MENUSU } from "../lib/menu";
import Kabuk from "./Kabuk";
import UygulamaYukle from "./UygulamaYukle";

export default function VeliYerlesim() {
  return <Kabuk menu={VELI_MENUSU} sekmeler={VELI_MENUSU[0].ogeler} yerlesim="ust" ustIcerik={<UygulamaYukle />} />;
}
