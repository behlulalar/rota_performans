#!/usr/bin/env bash
# Yerel E2E çalıştırıcı. Geliştirme veritabanına (rota) DOKUNMAZ:
#   - ayrı veritabanı: rota_e2e (her çalıştırmada düşürülüp yeniden oluşturulur)
#   - ayrı Redis dizini: 2
#   - ayrı backend konteyneri (127.0.0.1:8101) ve ayrı vite sunucusu (127.0.0.1:5175)
# Kullanım: bash e2e/yerel-calistir.sh [playwright argümanları]
set -euo pipefail

KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KOK"

export E2E_ADMIN_GIRIS="${E2E_ADMIN_GIRIS:-e2e.yonetici@example.com}"
export E2E_ADMIN_SIFRE="${E2E_ADMIN_SIFRE:-e2e-yonetici-sifresi-123}"
export E2E_BASE_URL="${E2E_BASE_URL:-http://127.0.0.1:5175}"

BACKEND=rota-e2e-backend
FRONTEND=rota-e2e-frontend
VERITABANI=rota_e2e

temizle() {
  echo "==> E2E konteynerleri kapatılıyor"
  docker rm -f "$BACKEND" "$FRONTEND" >/dev/null 2>&1 || true
  docker compose exec -T db psql -U rota -d postgres -qc "DROP DATABASE IF EXISTS $VERITABANI WITH (FORCE)" >/dev/null 2>&1 || true
}
trap temizle EXIT

bekle() { # bekle <url> <ad>
  for _ in $(seq 1 90); do
    if curl -fsS "$1" >/dev/null 2>&1; then echo "    $2 hazır"; return 0; fi
    sleep 1
  done
  echo "HATA: $2 zamanında hazır olmadı ($1)" >&2
  docker logs --tail 40 "$BACKEND" >&2 || true
  docker logs --tail 40 "$FRONTEND" >&2 || true
  return 1
}

echo "==> Altyapı (db, redis)"
docker compose up -d --wait db redis
docker rm -f "$BACKEND" "$FRONTEND" >/dev/null 2>&1 || true

echo "==> $VERITABANI sıfırlanıyor, Redis dizini 2 temizleniyor"
docker compose exec -T db psql -U rota -d postgres -qc "DROP DATABASE IF EXISTS $VERITABANI WITH (FORCE)"
docker compose exec -T db psql -U rota -d postgres -qc "CREATE DATABASE $VERITABANI"
docker compose exec -T redis redis-cli -n 2 flushdb >/dev/null

echo "==> E2E backend ($BACKEND, 127.0.0.1:8101)"
docker compose build backend >/dev/null
docker compose run -d --rm --no-deps --name "$BACKEND" -p 127.0.0.1:8101:8000 \
  -e ENV=e2e \
  -e DATABASE_URL="postgresql+asyncpg://rota:rota_dev_sifre@db:5432/$VERITABANI" \
  -e REDIS_URL=redis://redis:6379/2 \
  -e DOSYA_DIZINI=/tmp/e2e-uploads \
  -e COOKIE_SECURE=false \
  backend uvicorn app.main:app --host 0.0.0.0 --port 8000 >/dev/null
docker exec "$BACKEND" alembic upgrade head
docker exec -e E2E_ADMIN_GIRIS -e E2E_ADMIN_SIFRE "$BACKEND" python -m app.cli e2e-tohum
bekle http://127.0.0.1:8101/api/saglik "E2E backend"

echo "==> E2E frontend ($FRONTEND, 127.0.0.1:5175)"
docker compose run -d --rm --no-deps --name "$FRONTEND" -p 127.0.0.1:5175:5173 \
  -e API_PROXY_TARGET="http://$BACKEND:8000" \
  frontend sh -c "{ [ -x node_modules/.bin/vite ] && [ node_modules/.package-lock.json -nt package-lock.json ]; } || npm ci; npx vite --host 0.0.0.0 --port 5173" >/dev/null
# Vite üzerinden /api'ye ulaşılabiliyorsa proxy ve ağ adları doğru kurulmuştur.
bekle http://127.0.0.1:5175/api/saglik "E2E frontend (proxy dahil)"

echo "==> Playwright"
cd "$KOK/e2e"
if [ ! -d node_modules ]; then npm install; fi
npx playwright install chromium >/dev/null
# "Bugün" hesabı backend ile aynı saat diliminde yapılsın.
TZ=Europe/Istanbul npx playwright test "$@"
