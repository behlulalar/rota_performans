from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str
    redis_url: str
    jwt_secret: str
    # Her biri 32 bayt, urlsafe base64. Üretimde ayrı ayrı üretilir ve yedeği güvenli yerde tutulur:
    # şifreleme anahtarı kaybolursa kayıtlı kimlik numaraları geri okunamaz.
    kimlik_sifreleme_anahtari: str
    kimlik_ozet_anahtari: str
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    # "Beni hatırla": açıkken oturum bu kadar gün (kayan) sürer, çerez kalıcıdır.
    hatirla_gun: int = 30
    # Kapalıyken oturum bu kadar saat sürer, çerez oturum çerezidir.
    hatirlamasiz_saat: int = 12
    cookie_secure: bool = True
    cors_origins: str = ""
    # Yüklenen fotoğrafların kök dizini (herkese açık sunulmaz, yalnızca API üzerinden okunur).
    dosya_dizini: str = "/app/uploads"
    # "Bugün" ve ders saatleri bu saat dilimine göre hesaplanır.
    saat_dilimi: str = "Europe/Istanbul"
    # Web Push (VAPID). Üçü de doluysa push gönderimi açıktır. Anahtar üretimi: python -m app.cli vapid-uret
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = ""  # mailto:kulup@ornek.com

    @property
    def push_etkin(self) -> bool:
        return bool(self.vapid_public_key and self.vapid_private_key and self.vapid_subject)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"


settings = Settings()
