import json
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app import totp as totp_modulu
from app import telefon as telefon_modulu
from app.api.antrenorler import GIRIS_TEKRAR, TELEFON_TEKRAR, _giris_hazirla, cakisma_denetle
from app.config import settings
from app.db import get_session
from app.deps import aktif_kullanici_serbest
from app.models.kullanici import Kullanici, Oturum, Rol
from app.models.ogrenci import IletisimKisisi
from app.models.program import Antrenor
from app.ratelimit import get_redis, izin_var_mi
from app.security import (
    belirtec_ozeti,
    erisim_belirteci_uret,
    normalize_giris,
    ozet_yenilenmeli_mi,
    sahte_dogrulama,
    sifre_dogru_mu,
    sifre_ozeti,
    simdi,
    yenileme_belirteci_uret,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_ADI = "rota_yenileme"
COOKIE_YOLU = "/api/auth"

# dakikada, IP başına. E2E testleri tek IP'den çok sayıda giriş yaptığı için orada gevşektir.
IP_LIMITI = 1000 if settings.env == "e2e" else 20
HESAP_DENEME_LIMITI = 5
HESAP_KILIT_DAKIKA = 15

PANEL_ROLLERI = {
    "veli": {Rol.veli, Rol.ogrenci},
    "antrenor": {Rol.antrenor},
    "yonetici": {Rol.admin},
    # Teknik destek yalnız kendi panelinden girer; yönetici de buradan giremez.
    "destek": {Rol.destek},
}

# Şifresi doğru girilen destek hesabı tam oturum almaz; kısa ömürlü "2FA bekleyen" belirteci alır (Redis).
BEKLEYEN_TTL = 300
IKILI_KULLANICI_LIMITI = 10  # 5 dakikada, hesap başına (kilit mantığına ek)

# Hesabın var olup olmadığını sızdırmamak için tüm başarısız girişler aynı yanıtı verir.
GENEL_HATA = "Giriş bilgileri hatalı veya hesap geçici olarak kilitli."


class LoginIstegi(BaseModel):
    giris: str = Field(min_length=3, max_length=255)
    sifre: str = Field(min_length=1, max_length=256)
    beni_hatirla: bool = False
    # Giriş sayfasının paneli. Verilirse yalnız o panelin rolleri girebilir (yanlış panel = hatalı şifre gibi reddedilir).
    # Yetki yine her istekte rolden verilir; bu alan yalnız kullanıcıyı doğru sayfaya yönlendirmek içindir.
    # "destek" paneli yalnız destek rolüne açıktır; destek hesabı panel verilmeden de giremez.
    panel: Literal["veli", "antrenor", "yonetici", "destek"] | None = None


class BekleyenIstegi(BaseModel):
    bekleyen_belirtec: str = Field(min_length=16, max_length=128)


class KodIstegi(BekleyenIstegi):
    # 6 haneli TOTP kodu ya da kurtarma kodu (xxxxx-xxxxx).
    kod: str = Field(min_length=1, max_length=32)


class IkiAdimYaniti(BaseModel):
    """Destek hesabı şifreyle girince dönen yanıt: henüz oturum yok, 2. adım gerekli."""

    iki_adim: bool = True
    # "kurulum": TOTP hiç kurulmamış; "dogrulama": kurulu, kod istenir.
    durum: Literal["kurulum", "dogrulama"]
    bekleyen_belirtec: str
    expires_in: int = BEKLEYEN_TTL


class KurulumYaniti(BaseModel):
    gizli_anahtar: str
    otpauth_uri: str


class SifreDegistirIstegi(BaseModel):
    mevcut_sifre: str = Field(min_length=1, max_length=256)
    yeni_sifre: str = Field(max_length=256)


class GirisDegistirIstegi(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    yeni_giris: str = Field(min_length=1, max_length=255)
    sifre: str = Field(min_length=1, max_length=256)


class TelefonDegistirIstegi(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # Boş/None: telefonu kaldırır.
    telefon: str | None = Field(default=None, max_length=32)
    sifre: str = Field(min_length=1, max_length=256)


class BelirtecYaniti(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class KurulumTamamYaniti(BelirtecYaniti):
    # Yalnız bu yanıtta, bir kez gösterilir.
    kurtarma_kodlari: list[str]


class KullaniciYaniti(BaseModel):
    id: uuid.UUID
    rol: Rol
    giris: str
    ad_soyad: str | None = None
    sifre_degistirmeli: bool = False
    telefon: str | None = None


def _istemci_ip(request: Request) -> str:
    return request.client.host if request.client else "bilinmiyor"


def _bosta_suresi() -> timedelta:
    return timedelta(minutes=settings.bosta_dakika)


def _cookie_yaz(response: Response, belirtec: str, hatirla: bool) -> None:
    # Hatırlamasızda max_age/expires verilmez: tarayıcı kapanınca silinen oturum çerezi olur.
    response.set_cookie(
        COOKIE_ADI,
        belirtec,
        max_age=settings.hatirla_cerez_gun * 86400 if hatirla else None,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=COOKIE_YOLU,
    )


def _cookie_sil(response: Response) -> None:
    response.delete_cookie(COOKIE_ADI, path=COOKIE_YOLU)


async def _oturum_ac(
    session: AsyncSession, kullanici: Kullanici, hatirla: bool, bitis: datetime | None = None
) -> str:
    """Yeni yenileme belirteci oturumu. `bitis` verilmezse boşta süresi şimdiden başlar (giriş);
    yenilemede önceki oturumun bitişi korunur, böylece otomatik yenileme oturumu uzatmaz."""
    belirtec, ozet = yenileme_belirteci_uret()
    session.add(
        Oturum(
            kullanici_id=kullanici.id,
            token_ozeti=ozet,
            bitis=bitis or simdi() + _bosta_suresi(),
            hatirla=hatirla,
        )
    )
    return belirtec


def _belirtec_yaniti(kullanici: Kullanici) -> BelirtecYaniti:
    return BelirtecYaniti(
        access_token=erisim_belirteci_uret(kullanici.id, kullanici.rol),
        expires_in=settings.access_token_minutes * 60,
    )


@router.post("/login", response_model=BelirtecYaniti | IkiAdimYaniti)
async def login(
    govde: LoginIstegi,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    ip = _istemci_ip(request)
    if not await izin_var_mi(redis, f"rl:login:ip:{ip}", IP_LIMITI, 60):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Çok fazla deneme. Lütfen biraz bekleyin.")

    giris = normalize_giris(govde.giris)
    kullanici = (await session.execute(select(Kullanici).where(Kullanici.giris == giris))).scalar_one_or_none()
    if kullanici is None and "@" not in giris and telefon_modulu.giris_icin(giris) is not None:
        # İkinci giriş yolu: yalnız yönetici ve teknik destek telefon alanı. Antrenör/veli yalnız kendi girişiyle girer.
        kullanici = (
            await session.execute(
                select(Kullanici).where(Kullanici.telefon == giris, Kullanici.rol.in_((Rol.admin, Rol.destek)))
            )
        ).scalar_one_or_none()
    simdi_ = simdi()

    kilitli = kullanici is not None and kullanici.kilit_bitis is not None and kullanici.kilit_bitis > simdi_
    if kullanici is None or kilitli:
        sahte_dogrulama(govde.sifre)
        await audit.kaydet(
            session,
            "giris_basarisiz",
            kullanici_id=kullanici.id if kullanici else None,
            ip=ip,
            detay={"neden": "kilitli" if kilitli else "bilinmeyen_hesap"},
        )
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENEL_HATA)

    if govde.panel is None:
        # Panel verilmeyen genel girişte destek hesabı reddedilir: yalnız destek panelinden girer.
        panel_uygun = kullanici.rol != Rol.destek
    else:
        panel_uygun = kullanici.rol in PANEL_ROLLERI[govde.panel]
    if not (sifre_dogru_mu(kullanici.sifre_ozeti, govde.sifre) and kullanici.aktif and panel_uygun):
        kullanici.basarisiz_deneme += 1
        detay = {"neden": "hatali_sifre" if panel_uygun else "yanlis_panel"}
        if kullanici.basarisiz_deneme >= HESAP_DENEME_LIMITI:
            kullanici.kilit_bitis = simdi_ + timedelta(minutes=HESAP_KILIT_DAKIKA)
            kullanici.basarisiz_deneme = 0
            detay["kilitlendi"] = True
        await audit.kaydet(session, "giris_basarisiz", kullanici_id=kullanici.id, ip=ip, detay=detay)
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENEL_HATA)

    if ozet_yenilenmeli_mi(kullanici.sifre_ozeti):
        kullanici.sifre_ozeti = sifre_ozeti(govde.sifre)
    if kullanici.rol == Rol.destek:
        # Şifre tek başına yetmez: sayaç sıfırlanmaz (yoksa 2. adım denemeleri sınırsız tekrarlanırdı),
        # oturum verilmez, kod doğrulanana kadar bekleyen belirteç döner.
        bekleyen = await _bekleyen_olustur(redis, kullanici.id, govde.beni_hatirla)
        await audit.kaydet(session, "giris_sifre_dogru_ikili_bekliyor", kullanici_id=kullanici.id, ip=ip)
        await session.commit()
        return IkiAdimYaniti(durum="dogrulama" if kullanici.totp_aktif else "kurulum", bekleyen_belirtec=bekleyen)

    return await _tam_oturum(session, response, kullanici, govde.beni_hatirla, ip)


def _bekleyen_anahtar(belirtec: str) -> str:
    return f"2fa:bekleyen:{belirtec_ozeti(belirtec)}"


async def _bekleyen_olustur(redis: Redis, kullanici_id: uuid.UUID, hatirla: bool) -> str:
    belirtec = secrets.token_urlsafe(32)
    await redis.set(
        _bekleyen_anahtar(belirtec), json.dumps({"k": str(kullanici_id), "h": hatirla}), ex=BEKLEYEN_TTL
    )
    return belirtec


async def _tam_oturum(
    session: AsyncSession, response: Response, kullanici: Kullanici, hatirla: bool, ip: str, ikili: bool = False
) -> BelirtecYaniti:
    kullanici.basarisiz_deneme = 0
    kullanici.kilit_bitis = None
    kullanici.son_giris = simdi()
    belirtec = await _oturum_ac(session, kullanici, hatirla)
    await audit.kaydet(
        session, "giris_basarili", kullanici_id=kullanici.id, ip=ip, detay={"ikili_dogrulama": True} if ikili else None
    )
    await session.commit()

    _cookie_yaz(response, belirtec, hatirla)
    return _belirtec_yaniti(kullanici)


async def _bekleyen_coz(
    request: Request, redis: Redis, session: AsyncSession, bekleyen_belirtec: str
) -> tuple[Kullanici, bool]:
    """Bekleyen belirteci doğrular ve hesabı kilitleyerek döner. Her hatada aynı genel yanıt verilir."""
    ip = _istemci_ip(request)
    if not await izin_var_mi(redis, f"rl:2fa:ip:{ip}", IP_LIMITI, 60):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Çok fazla deneme. Lütfen biraz bekleyin.")
    ham = await redis.get(_bekleyen_anahtar(bekleyen_belirtec))
    suresi_doldu = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Doğrulama süresi doldu, lütfen şifrenizle yeniden giriş yapın."
    )
    if ham is None:
        raise suresi_doldu
    veri = json.loads(ham)
    kullanici = (
        await session.execute(select(Kullanici).where(Kullanici.id == uuid.UUID(veri["k"])).with_for_update())
    ).scalar_one_or_none()
    if kullanici is None or not kullanici.aktif or kullanici.rol != Rol.destek:
        raise suresi_doldu
    if kullanici.kilit_bitis is not None and kullanici.kilit_bitis > simdi():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENEL_HATA)
    if not await izin_var_mi(redis, f"rl:2fa:kullanici:{kullanici.id}", IKILI_KULLANICI_LIMITI, 300):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Çok fazla deneme. Lütfen biraz bekleyin.")
    return kullanici, bool(veri.get("h"))


async def _kod_hatasi(
    session: AsyncSession, redis: Redis, kullanici: Kullanici, bekleyen_belirtec: str, ip: str, neden: str
) -> HTTPException:
    """Başarısız 2. adım denemesi şifre denemesiyle aynı sayaca ve kilide yazılır."""
    kullanici.basarisiz_deneme += 1
    detay = {"neden": neden}
    if kullanici.basarisiz_deneme >= HESAP_DENEME_LIMITI:
        kullanici.kilit_bitis = simdi() + timedelta(minutes=HESAP_KILIT_DAKIKA)
        kullanici.basarisiz_deneme = 0
        detay["kilitlendi"] = True
        await redis.delete(_bekleyen_anahtar(bekleyen_belirtec))
    await audit.kaydet(session, "ikili_dogrulama_basarisiz", kullanici_id=kullanici.id, ip=ip, detay=detay)
    await session.commit()
    if detay.get("kilitlendi"):
        return HTTPException(status.HTTP_401_UNAUTHORIZED, GENEL_HATA)
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Doğrulama kodu hatalı")


@router.post("/2fa/kurulum", response_model=KurulumYaniti)
async def ikili_kurulum(
    govde: BekleyenIstegi,
    request: Request,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    """Kurulu olmayan destek hesabı için gizli anahtar üretir (kod doğrulanana kadar etkin değildir).
    Çağrı tekrarlanırsa henüz doğrulanmamış anahtar yenilenir."""
    kullanici, _ = await _bekleyen_coz(request, redis, session, govde.bekleyen_belirtec)
    if kullanici.totp_aktif:
        raise HTTPException(status.HTTP_409_CONFLICT, "İki adımlı doğrulama zaten kurulu")
    gizli = totp_modulu.gizli_uret()
    kullanici.totp_sifreli = totp_modulu.sifrele(gizli)
    await audit.kaydet(session, "ikili_kurulum_basladi", kullanici_id=kullanici.id, ip=_istemci_ip(request))
    await session.commit()
    return KurulumYaniti(gizli_anahtar=gizli, otpauth_uri=totp_modulu.uri(gizli, kullanici.giris))


@router.post("/2fa/kurulum-dogrula", response_model=KurulumTamamYaniti)
async def ikili_kurulum_dogrula(
    govde: KodIstegi,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    """Uygulamadaki ilk kodu doğrular: 2FA etkinleşir, oturum açılır, 8 kurtarma kodu bir kez gösterilir."""
    ip = _istemci_ip(request)
    kullanici, hatirla = await _bekleyen_coz(request, redis, session, govde.bekleyen_belirtec)
    if kullanici.totp_aktif:
        raise HTTPException(status.HTTP_409_CONFLICT, "İki adımlı doğrulama zaten kurulu")
    if kullanici.totp_sifreli is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Önce kurulumu başlatın")
    kod = totp_modulu.kod_normalize(govde.kod)
    if not await totp_modulu.kod_dogru_mu(redis, kullanici.id, totp_modulu.coz(kullanici.totp_sifreli), kod):
        raise await _kod_hatasi(session, redis, kullanici, govde.bekleyen_belirtec, ip, "hatali_kod_kurulum")

    kodlar, ozetler = totp_modulu.kurtarma_kodlari_uret()
    kullanici.totp_aktif = True
    kullanici.totp_kurtarma = ozetler
    await audit.kaydet(session, "ikili_kurulum_tamamlandi", kullanici_id=kullanici.id, ip=ip)
    await redis.delete(_bekleyen_anahtar(govde.bekleyen_belirtec))
    yanit = await _tam_oturum(session, response, kullanici, hatirla, ip, ikili=True)
    return KurulumTamamYaniti(**yanit.model_dump(), kurtarma_kodlari=kodlar)


@router.post("/2fa/dogrula", response_model=BelirtecYaniti)
async def ikili_dogrula(
    govde: KodIstegi,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    """Kurulu 2FA için 6 haneli kodu ya da bir kurtarma kodunu (tek kullanımlık) doğrular ve oturum açar."""
    ip = _istemci_ip(request)
    kullanici, hatirla = await _bekleyen_coz(request, redis, session, govde.bekleyen_belirtec)
    if not kullanici.totp_aktif or kullanici.totp_sifreli is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "İki adımlı doğrulama kurulu değil")
    kod = totp_modulu.kod_normalize(govde.kod)
    kurtarma_kullanildi = False
    if totp_modulu.kod_biciminde_mi(kod):
        dogru = await totp_modulu.kod_dogru_mu(redis, kullanici.id, totp_modulu.coz(kullanici.totp_sifreli), kod)
    else:
        ozet = totp_modulu.kurtarma_ozeti(kod)
        kalan = list(kullanici.totp_kurtarma or [])
        dogru = ozet in kalan
        if dogru:
            kalan.remove(ozet)  # tek kullanımlık
            kullanici.totp_kurtarma = kalan
            kurtarma_kullanildi = True
    if not dogru:
        raise await _kod_hatasi(session, redis, kullanici, govde.bekleyen_belirtec, ip, "hatali_kod")

    if kurtarma_kullanildi:
        await audit.kaydet(
            session, "ikili_kurtarma_kodu_kullanildi", kullanici_id=kullanici.id, ip=ip,
            detay={"kalan": len(kullanici.totp_kurtarma)},
        )
    await redis.delete(_bekleyen_anahtar(govde.bekleyen_belirtec))
    return await _tam_oturum(session, response, kullanici, hatirla, ip, ikili=True)


@router.post("/refresh", response_model=BelirtecYaniti)
async def yenile(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    yenileme: str | None = Cookie(default=None, alias=COOKIE_ADI),
):
    def reddet() -> HTTPException:
        _cookie_sil(response)
        return HTTPException(status.HTTP_401_UNAUTHORIZED, "Oturum süresi doldu, lütfen yeniden giriş yapın.")

    if not yenileme:
        raise reddet()

    oturum = (
        await session.execute(
            select(Oturum).where(Oturum.token_ozeti == belirtec_ozeti(yenileme)).with_for_update()
        )
    ).scalar_one_or_none()
    if oturum is None or oturum.bitis < simdi():
        raise reddet()

    if oturum.iptal:
        # Kullanılmış belirteç tekrar geldi: çalınmış olabilir, kullanıcının tüm oturumlarını kapat.
        await session.execute(update(Oturum).where(Oturum.kullanici_id == oturum.kullanici_id).values(iptal=True))
        await audit.kaydet(
            session, "yenileme_yeniden_kullanim", kullanici_id=oturum.kullanici_id, ip=_istemci_ip(request)
        )
        await session.commit()
        raise reddet()

    kullanici = await session.get(Kullanici, oturum.kullanici_id)
    if kullanici is None or not kullanici.aktif:
        raise reddet()

    oturum.iptal = True
    # Bitiş korunur (eski uzun ömürlü oturumlar da en geç şimdi + boşta süresine indirilir).
    yeni = await _oturum_ac(session, kullanici, oturum.hatirla, min(oturum.bitis, simdi() + _bosta_suresi()))
    await session.commit()

    _cookie_yaz(response, yeni, oturum.hatirla)
    return _belirtec_yaniti(kullanici)


@router.post("/etkinlik", status_code=status.HTTP_204_NO_CONTENT)
async def etkinlik(
    session: AsyncSession = Depends(get_session),
    yenileme: str | None = Cookie(default=None, alias=COOKIE_ADI),
):
    """Kullanıcı hareketi bildirimi: boşta süresini şimdiden yeniden başlatır. Yalnız geçerli oturumda çalışır."""
    oturum = None
    if yenileme:
        oturum = (
            await session.execute(select(Oturum).where(Oturum.token_ozeti == belirtec_ozeti(yenileme)).with_for_update())
        ).scalar_one_or_none()
    if oturum is None or oturum.iptal or oturum.bitis < simdi():
        # Çerez silinmez: eşzamanlı bir yenileme belirteci az önce döndürmüş olabilir (yeni çerez bozulmasın).
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Oturum süresi doldu, lütfen yeniden giriş yapın.")
    oturum.bitis = simdi() + _bosta_suresi()
    await session.commit()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def cikis(
    response: Response,
    session: AsyncSession = Depends(get_session),
    yenileme: str | None = Cookie(default=None, alias=COOKIE_ADI),
):
    if yenileme:
        await session.execute(
            update(Oturum).where(Oturum.token_ozeti == belirtec_ozeti(yenileme)).values(iptal=True)
        )
        await session.commit()
    _cookie_sil(response)


@router.get("/me", response_model=KullaniciYaniti)
async def ben(kullanici: Kullanici = Depends(aktif_kullanici_serbest), session: AsyncSession = Depends(get_session)):
    ad = kullanici.ad_soyad
    if not ad:
        ad = (
            await session.execute(select(Antrenor.ad_soyad).where(Antrenor.kullanici_id == kullanici.id).limit(1))
        ).scalar_one_or_none()
    if not ad:
        ad = (
            await session.execute(
                select(IletisimKisisi.ad_soyad)
                .where(IletisimKisisi.kullanici_id == kullanici.id)
                .order_by(IletisimKisisi.birincil.desc(), IletisimKisisi.olusturma)
                .limit(1)
            )
        ).scalar_one_or_none()
    return KullaniciYaniti(
        id=kullanici.id, rol=kullanici.rol, giris=kullanici.giris, ad_soyad=ad or None,
        sifre_degistirmeli=kullanici.sifre_degistirmeli, telefon=kullanici.telefon,
    )


def _yeni_sifre_hatasi(mevcut: str, yeni: str) -> str | None:
    if len(yeni) < 10:
        return "Yeni şifre en az 10 karakter olmalı"
    if len(yeni) > 256:
        return "Yeni şifre en fazla 256 karakter olabilir"
    if not (any(c.isalpha() for c in yeni) and any(c.isdigit() for c in yeni)):
        return "Yeni şifre en az bir harf ve bir rakam içermeli"
    if yeni == mevcut:
        return "Yeni şifre mevcut şifreyle aynı olamaz"
    return None


@router.post("/sifre-degistir", status_code=status.HTTP_204_NO_CONTENT)
async def sifre_degistir(
    govde: SifreDegistirIstegi,
    request: Request,
    response: Response,
    kullanici: Kullanici = Depends(aktif_kullanici_serbest),
    session: AsyncSession = Depends(get_session),
    yenileme: str | None = Cookie(default=None, alias=COOKIE_ADI),
):
    ip = _istemci_ip(request)
    simdi_ = simdi()
    if kullanici.kilit_bitis is not None and kullanici.kilit_bitis > simdi_:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Hesap geçici olarak kilitli. Lütfen daha sonra deneyin.")

    if not sifre_dogru_mu(kullanici.sifre_ozeti, govde.mevcut_sifre):
        kullanici.basarisiz_deneme += 1
        detay = {"neden": "hatali_mevcut_sifre"}
        if kullanici.basarisiz_deneme >= HESAP_DENEME_LIMITI:
            kullanici.kilit_bitis = simdi_ + timedelta(minutes=HESAP_KILIT_DAKIKA)
            kullanici.basarisiz_deneme = 0
            detay["kilitlendi"] = True
        await audit.kaydet(session, "sifre_degistirme_basarisiz", kullanici_id=kullanici.id, ip=ip, detay=detay)
        await session.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mevcut şifre hatalı")

    hata = _yeni_sifre_hatasi(govde.mevcut_sifre, govde.yeni_sifre)
    if hata:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, hata)

    kullanici.sifre_ozeti = sifre_ozeti(govde.yeni_sifre)
    kullanici.sifre_degistirmeli = False
    kullanici.basarisiz_deneme = 0
    kullanici.kilit_bitis = None
    sorgu = update(Oturum).where(Oturum.kullanici_id == kullanici.id)
    if yenileme:
        sorgu = sorgu.where(Oturum.token_ozeti != belirtec_ozeti(yenileme))
    await session.execute(sorgu.values(iptal=True))
    await audit.kaydet(session, "sifre_degistirildi", kullanici_id=kullanici.id, ip=ip)
    await session.commit()


@router.patch("/giris", response_model=KullaniciYaniti)
async def giris_degistir(
    govde: GirisDegistirIstegi,
    request: Request,
    kullanici: Kullanici = Depends(aktif_kullanici_serbest),
    session: AsyncSession = Depends(get_session),
    yenileme: str | None = Cookie(default=None, alias=COOKIE_ADI),
):
    """Personelin (yönetici, teknik destek, antrenör) kendi giriş bilgisini, şifresini doğrulayarak değiştirmesi."""
    if kullanici.rol not in (Rol.admin, Rol.destek, Rol.antrenor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu işlem için yetkiniz yok")
    ip = _istemci_ip(request)
    simdi_ = simdi()
    if kullanici.kilit_bitis is not None and kullanici.kilit_bitis > simdi_:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Hesap geçici olarak kilitli. Lütfen daha sonra deneyin.")

    if not sifre_dogru_mu(kullanici.sifre_ozeti, govde.sifre):
        kullanici.basarisiz_deneme += 1
        detay = {"neden": "hatali_sifre"}
        if kullanici.basarisiz_deneme >= HESAP_DENEME_LIMITI:
            kullanici.kilit_bitis = simdi_ + timedelta(minutes=HESAP_KILIT_DAKIKA)
            kullanici.basarisiz_deneme = 0
            detay["kilitlendi"] = True
        await audit.kaydet(session, "giris_degistirme_basarisiz", kullanici_id=kullanici.id, ip=ip, detay=detay)
        await session.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Şifre hatalı")

    yeni = _giris_hazirla(govde.yeni_giris)
    if kullanici.rol == Rol.antrenor and "@" in yeni:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Antrenör girişi yalnız telefon olabilir")
    if yeni == kullanici.giris:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Yeni giriş bilgisi mevcut olanla aynı")
    if (await session.execute(select(Kullanici.id).where(Kullanici.giris == yeni))).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, GIRIS_TEKRAR)
    await cakisma_denetle(session, yeni, kullanici.id)

    kullanici.giris = yeni
    if kullanici.telefon == yeni:
        kullanici.telefon = None  # giriş zaten bu telefon; ikinci kayda gerek yok
    if kullanici.rol == Rol.antrenor and "@" not in yeni:
        # Antrenörün giriş telefonu ile antrenör kartındaki telefon ayrışmasın.
        await session.execute(update(Antrenor).where(Antrenor.kullanici_id == kullanici.id).values(telefon=yeni))
    kullanici.basarisiz_deneme = 0
    sorgu = update(Oturum).where(Oturum.kullanici_id == kullanici.id)
    if yenileme:
        sorgu = sorgu.where(Oturum.token_ozeti != belirtec_ozeti(yenileme))
    await session.execute(sorgu.values(iptal=True))
    await audit.kaydet(session, "giris_degisti", kullanici_id=kullanici.id, ip=ip)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, GIRIS_TEKRAR)
    return await ben(kullanici, session)


@router.patch("/telefon", response_model=KullaniciYaniti)
async def telefon_degistir(
    govde: TelefonDegistirIstegi,
    request: Request,
    kullanici: Kullanici = Depends(aktif_kullanici_serbest),
    session: AsyncSession = Depends(get_session),
    yenileme: str | None = Cookie(default=None, alias=COOKIE_ADI),
):
    """Yöneticinin/teknik desteğin kendi telefonunu (ikinci giriş yolu), şifresini doğrulayarak değiştirmesi veya kaldırması."""
    if kullanici.rol not in (Rol.admin, Rol.destek):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu işlem için yetkiniz yok")
    ip = _istemci_ip(request)
    simdi_ = simdi()
    if kullanici.kilit_bitis is not None and kullanici.kilit_bitis > simdi_:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Hesap geçici olarak kilitli. Lütfen daha sonra deneyin.")

    if not sifre_dogru_mu(kullanici.sifre_ozeti, govde.sifre):
        kullanici.basarisiz_deneme += 1
        detay = {"neden": "hatali_sifre"}
        if kullanici.basarisiz_deneme >= HESAP_DENEME_LIMITI:
            kullanici.kilit_bitis = simdi_ + timedelta(minutes=HESAP_KILIT_DAKIKA)
            kullanici.basarisiz_deneme = 0
            detay["kilitlendi"] = True
        await audit.kaydet(session, "telefon_degistirme_basarisiz", kullanici_id=kullanici.id, ip=ip, detay=detay)
        await session.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Şifre hatalı")

    yeni = None
    if govde.telefon:
        yeni = _giris_hazirla(govde.telefon)
        if "@" in yeni:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Geçerli bir telefon numarası girin")
        if yeni == kullanici.giris:
            yeni = None  # giriş zaten bu telefon
        elif yeni != kullanici.telefon:
            await cakisma_denetle(session, yeni, kullanici.id)
    if yeni == kullanici.telefon:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Telefon bilgisi değişmedi")

    kullanici.telefon = yeni
    kullanici.basarisiz_deneme = 0
    sorgu = update(Oturum).where(Oturum.kullanici_id == kullanici.id)
    if yenileme:
        sorgu = sorgu.where(Oturum.token_ozeti != belirtec_ozeti(yenileme))
    await session.execute(sorgu.values(iptal=True))
    await audit.kaydet(session, "telefon_degisti", kullanici_id=kullanici.id, ip=ip)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, TELEFON_TEKRAR)
    return await ben(kullanici, session)
