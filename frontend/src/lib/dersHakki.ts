/** Defterdeki bakiye eksiye düşebilir (paketten fazla ders işlenmişse); ekranlarda hep en az 0 gösterilir. */
export const gosterilenDers = (n: number): number => Math.max(0, n);
