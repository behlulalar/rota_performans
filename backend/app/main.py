from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    antrenorler,
    auth,
    genel_bakis,
    gruplar,
    odemeler,
    ogrenciler,
    oturumlar,
    paketler,
    raporlar,
    saglik,
)
from app.config import settings

app = FastAPI(
    title="Rota Performans Akademi",
    # Üretimde API şeması herkese açık olmasın.
    docs_url="/api/docs" if settings.is_dev else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.is_dev else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def guvenlik_basliklari(request: Request, call_next):
    yanit = await call_next(request)
    yanit.headers["X-Content-Type-Options"] = "nosniff"
    yanit.headers["X-Frame-Options"] = "DENY"
    yanit.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/api") and "Cache-Control" not in yanit.headers:
        yanit.headers["Cache-Control"] = "no-store"
    return yanit


app.include_router(saglik.router)
app.include_router(auth.router)
app.include_router(ogrenciler.router)
app.include_router(antrenorler.router)
app.include_router(gruplar.router)
app.include_router(paketler.router)
app.include_router(paketler.ogrenci_router)
app.include_router(paketler.ogrenci_paketi_router)
app.include_router(odemeler.ogrenci_paketi_router)
app.include_router(odemeler.router)
app.include_router(genel_bakis.router)
app.include_router(raporlar.router)
app.include_router(oturumlar.router)
