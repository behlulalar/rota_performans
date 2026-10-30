"""Teknik destek hesabı için parasal tutarların maskelenmesi (gerçek koruma sunucuda)."""
from pydantic import BaseModel

from app.models.kullanici import Kullanici, Rol


class _GizliTutar:
    """GizliTutar alanlarını işaretler; tutar_gizle yalnız bu işaretli alanları null yapar."""


GIZLI_TUTAR = _GizliTutar()


def _sifirla(deger) -> None:
    if isinstance(deger, BaseModel):
        for ad, alan in type(deger).model_fields.items():
            if GIZLI_TUTAR in alan.metadata:
                setattr(deger, ad, None)
            else:
                _sifirla(getattr(deger, ad))
    elif isinstance(deger, list):
        for oge in deger:
            _sifirla(oge)


def tutar_gizle[T](kullanici: Kullanici, yanit: T) -> T:
    """Teknik destek isteğinde yanıt şemasındaki tüm GizliTutar alanlarını (iç içe dahil) null yapar; diğer rollerde dokunmaz."""
    if kullanici.rol == Rol.destek:
        _sifirla(yanit)
    return yanit
