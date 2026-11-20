#!/usr/bin/env bash
# CANLI .env dosyasını rastgele sırlarla üretir. Var olan .env'in üzerine YAZMAZ. Sır değerlerini ekrana yazmaz.
# Kullanım (sunucuda, bu klasörde), tam olarak biri:
#   bash env-uret.sh --izinli +90XXXXXXXXXX   WhatsApp YALNIZ bu numaraya gider (ilk deneme için önerilir)
#   bash env-uret.sh --izinsiz                Kısıt yok: mesajlar GERÇEK velilere gider
# Mevcut bir yedeği geri yüklemek için kimlik anahtarlarını ortamdan verin (yoksa yenisi üretilir):
#   KIMLIK_SIFRELEME_ANAHTARI=... KIMLIK_OZET_ANAHTARI=... bash env-uret.sh --izinsiz
set -euo pipefail
cd "$(dirname "$0")"
umask 077
[ -e .env ] && { echo ".env zaten var; silmeden üzerine yazmıyorum." >&2; exit 1; }

KULLANIM="Kullanım: bash env-uret.sh --izinli +90XXXXXXXXXX  |  bash env-uret.sh --izinsiz"
IZINLI=""
case "${1:-}" in
  --izinli)
    [ "$#" -eq 2 ] || { echo "$KULLANIM" >&2; exit 1; }
    [[ "$2" =~ ^\+90[0-9]{10}$ ]] || { echo "Numara +90XXXXXXXXXX biçiminde olmalı." >&2; exit 1; }
    IZINLI="$2" ;;
  --izinsiz)
    [ "$#" -eq 1 ] || { echo "$KULLANIM" >&2; exit 1; } ;;
  *) echo "$KULLANIM" >&2; exit 1 ;;
esac

PG=$(openssl rand -hex 24)
SIFRELEME="${KIMLIK_SIFRELEME_ANAHTARI:-$(openssl rand -base64 32 | tr '+/' '-_')}"
OZET="${KIMLIK_OZET_ANAHTARI:-$(openssl rand -base64 32 | tr '+/' '-_')}"
cat > .env <<EOT
ENV=production
POSTGRES_PASSWORD=$PG
DATABASE_URL=postgresql+asyncpg://rota:$PG@db:5432/rota
REDIS_URL=redis://redis:6379/0
JWT_SECRET=$(openssl rand -hex 32)
KIMLIK_SIFRELEME_ANAHTARI=$SIFRELEME
KIMLIK_OZET_ANAHTARI=$OZET
COOKIE_SECURE=true
CORS_ORIGINS=https://veli.rotaperformans.com,https://yonetim.rotaperformans.com,https://antrenor.rotaperformans.com,https://destek.rotaperformans.com
PANEL_ALANI_KATI=true
DOSYA_DIZINI=/app/uploads
APP_SURUM=canli
EVOLUTION_URL=http://evolution:8080
EVOLUTION_API_KEY=$(openssl rand -hex 32)
EVOLUTION_INSTANCE=rota
# WhatsApp koruması: doluyken mesajlar YALNIZ bu numaralara gider; boşsa kısıt yoktur (gerçek veliler).
WHATSAPP_IZINLI_NUMARALAR=$IZINLI
# VAPID: ilk kurulumdan sonra "docker compose exec backend python -m app.cli vapid-uret" çıktısını buraya ekleyin.
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:behlulalar32@gmail.com
EOT
echo ".env üretildi (izin 600)."
if [ -z "$IZINLI" ]; then
  echo "UYARI: --izinsiz seçildi; WhatsApp mesajları GERÇEK velilere gidecek." >&2
fi
if [ -z "${KIMLIK_SIFRELEME_ANAHTARI:-}" ]; then
  echo "KIMLIK_SIFRELEME_ANAHTARI ve KIMLIK_OZET_ANAHTARI yeni üretildi: .env dosyasının yedeğini güvenli bir yere alın (kaybolursa T.C. numaraları okunamaz)."
fi
