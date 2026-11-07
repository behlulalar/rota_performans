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
    # Boşta kalma süresi (dakika): oturum, son kullanıcı hareketinden bu kadar sonra geçersiz olur.
    # Süre yalnız gerçek hareketle (POST /api/auth/etkinlik) uzar; arka plandaki otomatik yenileme uzatmaz.
    bosta_dakika: int = 30
    # "Beni hatırla": yalnız çerezin tarayıcı kapanınca silinip silinmeyeceğini belirler (gün).
    hatirla_cerez_gun: int = 30
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
    # WhatsApp (Evolution API). URL ve anahtar doluysa bağlantı ekranı açılır.
    evolution_url: str = ""
    evolution_api_key: str = ""
    evolution_instance: str = "rota"
    # Demo/test koruması: doluysa WhatsApp YALNIZ bu numaralara (virgülle ayrılmış, +90... biçimi) gider;
    # diğerlerinin bildirimi iptal edilir. Örnek verideki sahte numaralar gerçek kişilere ait olabilir.
    whatsapp_izinli_numaralar: str = ""

    # Sürüm bilgisi (derleme sırasında ortamdan verilir; yoksa destek ekranı "geliştirme" gösterir).
    app_surum: str = ""
    git_sha: str = ""

    @property
    def surum(self) -> str:
        return self.app_surum or self.git_sha or "geliştirme"

    @property
    def push_etkin(self) -> bool:
        return bool(self.vapid_public_key and self.vapid_private_key and self.vapid_subject)

    @property
    def whatsapp_etkin(self) -> bool:
        return bool(self.evolution_url and self.evolution_api_key)

    @property
    def whatsapp_izinli_liste(self) -> list[str]:
        return [n.strip() for n in self.whatsapp_izinli_numaralar.split(",") if n.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"


settings = Settings()
