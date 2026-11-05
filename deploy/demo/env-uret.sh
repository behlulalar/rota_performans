#!/usr/bin/env bash
# .env dosyasını rastgele sırlarla üretir. Var olan .env'in üzerine YAZMAZ.
# Kullanım (sunucuda, bu klasörde):  bash env-uret.sh +905XXXXXXXXX
#   argüman: WhatsApp'ın mesaj gönderebileceği TEK izinli numara (kendi numaranız, +90... biçiminde).
set -euo pipefail
cd "$(dirname "$0")"
[ -e .env ] && { echo ".env zaten var; silmeden üzerine yazmıyorum." >&2; exit 1; }
IZINLI="${1:-}"
[ -n "$IZINLI" ] || { echo "Kullanım: bash env-uret.sh +905XXXXXXXXX (izinli WhatsApp numarası)" >&2; exit 1; }
PG=$(openssl rand -hex 24)
umask 077
cat > .env <<EOF
ENV=demo
POSTGRES_PASSWORD=$PG
DATABASE_URL=postgresql+asyncpg://rota:$PG@db:5432/rota
REDIS_URL=redis://redis:6379/0
JWT_SECRET=$(openssl rand -hex 32)
KIMLIK_SIFRELEME_ANAHTARI=$(openssl rand -base64 32 | tr '+/' '-_')
KIMLIK_OZET_ANAHTARI=$(openssl rand -base64 32 | tr '+/' '-_')
COOKIE_SECURE=true
CORS_ORIGINS=https://rota.behlulalar.online
DOSYA_DIZINI=/app/uploads
APP_SURUM=demo
EVOLUTION_URL=http://evolution:8080
EVOLUTION_API_KEY=$(openssl rand -hex 32)
EVOLUTION_INSTANCE=rota
# Demo koruması: WhatsApp YALNIZ bu numaraya gider (örnek veri gerçek kişilerin numaralarına benzer).
WHATSAPP_IZINLI_NUMARALAR=$IZINLI
# VAPID: ilk kurulumdan sonra "docker compose run --rm backend python -m app.cli vapid-uret" çıktısını buraya ekleyin.
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:behlulalar32@gmail.com
EOF
echo ".env üretildi (izin 600). KIMLIK_SIFRELEME_ANAHTARI'nın yedeğini güvenli bir yere alın."
