import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.manuel_kayit import ManuelKayitTuru
from app.models.paket import OdemeYontemi
from app.schemas.paket import GizliTutar


class ManuelKayitGirdi(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    tur: ManuelKayitTuru
    tutar: Decimal = Field(gt=0, le=Decimal("99999999.99"), decimal_places=2)
    tarih: date
    yontem: OdemeYontemi
    aciklama: str = Field(min_length=3, max_length=200)


class ManuelKayitIptal(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    neden: str = Field(min_length=3, max_length=200)


class ManuelKayitYanit(BaseModel):
    id: uuid.UUID
    tur: ManuelKayitTuru
    tutar: GizliTutar
    tarih: date
    yontem: OdemeYontemi
    aciklama: str
    olusturan: str | None
    olusturma: datetime
    iptal: bool
    iptal_nedeni: str | None
