# Rota Performans Akademi

Yüzme kulübü yönetim sistemi. Planlar ve kararlar: [docs/](docs/).

## Geliştirme ortamı

Gereken: Docker. Portlar yalnızca `127.0.0.1`'e açılır ve makinedeki diğer servislerle çakışmasın diye varsayılandan farklıdır.

```bash
cp .env.example .env
sed -i '' "s/^JWT_SECRET=.*/JWT_SECRET=$(openssl rand -hex 32)/" .env   # macOS
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

| Servis | Adres |
|---|---|
| Arayüz | http://localhost:5174 |
| API | http://localhost:8100/api/saglik (geliştirmede şema: `/api/docs`) |
| PostgreSQL | `127.0.0.1:5434` (kullanıcı `rota`, veritabanı `rota`) |
| Redis | `127.0.0.1:6380` |

### Yönetici hesabı oluşturma
```bash
docker compose exec backend python -m app.cli admin-olustur ornek@kulup.com
```
Şifre en az 12 karakter olmalı ve komut satırından sorulur, geçmişe yazılmaz.

### Test
```bash
docker compose exec backend pytest -q
```
Testler `rota_test` veritabanını ve Redis 1. dizinini kullanır, geliştirme verisine dokunmaz.

### Yeni veritabanı geçişi
```bash
docker compose exec backend alembic revision --autogenerate -m "aciklama"
docker compose exec backend alembic upgrade head
```

## Yapı
```
backend/    FastAPI, SQLAlchemy, Alembic
frontend/   Vite + React + TypeScript + Tailwind
infra/      Veritabanı başlangıç betikleri (sunucu yapılandırmaları buraya gelecek)
docs/       Planlar. Müşteri/sözleşme dosyaları (pdf, docx) depoya girmez.
```

## Kurallar
- Gerçek öğrenci/veli verisi geliştirmede kullanılmaz. Sahte veri kullanılır.
- `.env` ve sırlar depoya girmez.
- Yetki kontrolü her uç noktada sunucuda yapılır ([docs/guvenlik-plani.md](docs/guvenlik-plani.md)).
