from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Kısıt adlarını sabitler, böylece Alembic geçişleri öngörülebilir olur.
NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def enum_kolon(enum_sinifi, uzunluk: int = 24):
    """Metin olarak saklanan, veritabanında CHECK ile korunan enum sütunu."""
    from sqlalchemy import Enum

    return Enum(
        enum_sinifi,
        native_enum=False,
        length=uzunluk,
        create_constraint=True,
        name=enum_sinifi.__name__.lower(),
    )
