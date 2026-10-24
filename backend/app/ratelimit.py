from collections.abc import AsyncIterator

from redis.asyncio import Redis

from app.config import settings


async def get_redis() -> AsyncIterator[Redis]:
    istemci = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield istemci
    finally:
        await istemci.aclose()


async def izin_var_mi(redis: Redis, anahtar: str, limit: int, pencere_sn: int) -> bool:
    """Sabit pencereli sayaç. Limit aşılınca False döner."""
    sayi = await redis.incr(anahtar)
    if sayi == 1:
        await redis.expire(anahtar, pencere_sn)
    return sayi <= limit
