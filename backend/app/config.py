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
    cookie_secure: bool = True
    cors_origins: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"


settings = Settings()
