import havuz from "../assets/havuz-arka-plan.webp";

/** Havuz görselinin bulanık, zemin rengiyle örtülü hâli; üst kapsayıcı `relative isolate` olmalı. */
export default function ArkaPlan() {
  return (
    <div aria-hidden="true" className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
      <img src={havuz} alt="" className="size-full object-cover scale-110 blur-[6px]" />
      {/* Zemin rengiyle örtü: yazılar her iki temada da rahat okunur. */}
      <div className="absolute inset-0 bg-zemin/80" />
    </div>
  );
}
