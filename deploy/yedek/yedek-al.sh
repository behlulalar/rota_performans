#!/usr/bin/env bash
# Rota Performans: şifreli tek paket yedek (veritabanı + yüklenen dosyalar + manifest).
# shellcheck disable=SC2016  # tek tırnaklı sh -c ifadeleri bilerek konteyner içinde açılır
# Kullanım:  bash yedek-al.sh <compose-dizini>
# Ortam değişkenleri: YEDEK_DIZINI (/var/backups/rota), YEDEK_ALICI (/etc/rota/yedek-alici.txt), SAKLAMA_GUN (14)
set -euo pipefail
umask 077

COMPOSE_DIZINI="${1:-}"
[ -n "$COMPOSE_DIZINI" ] || { echo "Kullanım: bash yedek-al.sh <compose-dizini>" >&2; exit 1; }
[ -f "$COMPOSE_DIZINI/docker-compose.yml" ] || { echo "HATA: $COMPOSE_DIZINI/docker-compose.yml bulunamadı." >&2; exit 1; }
YEDEK_DIZINI="${YEDEK_DIZINI:-/var/backups/rota}"
YEDEK_ALICI="${YEDEK_ALICI:-/etc/rota/yedek-alici.txt}"
SAKLAMA_GUN="${SAKLAMA_GUN:-14}"

command -v age >/dev/null || { echo "HATA: 'age' kurulu değil (apt install age)." >&2; exit 1; }
[ -s "$YEDEK_ALICI" ] || { echo "HATA: alıcı (genel anahtar) dosyası yok veya boş: $YEDEK_ALICI" >&2; exit 1; }
case "$SAKLAMA_GUN" in ''|*[!0-9]*) echo "HATA: SAKLAMA_GUN sayı olmalı." >&2; exit 1;; esac

mkdir -p "$YEDEK_DIZINI"
chmod 700 "$YEDEK_DIZINI"
GECICI="$(mktemp -d "$YEDEK_DIZINI/.gecici.XXXXXX")"
DAMGA="$(date +%Y%m%d-%H%M%S)"
HEDEF="$YEDEK_DIZINI/rota-$DAMGA.tar.age"
PARCA="$HEDEF.part"
temizle() { rm -rf "$GECICI"; rm -f "$PARCA"; }
trap temizle EXIT

cd "$COMPOSE_DIZINI"
dc() { docker compose "$@"; }
psql_sorgu() { dc exec -T db psql -U rota -d rota -At -c "$1"; }

echo "Veritabanı dökümü alınıyor..."
dc exec -T db pg_dump -Fc -U rota -d rota > "$GECICI/rota.dump"
[ -s "$GECICI/rota.dump" ] || { echo "HATA: rota.dump boş." >&2; exit 1; }

echo "Yüklenen dosyalar arşivleniyor..."
dc exec -T backend sh -c 'D="${DOSYA_DIZINI:-/app/uploads}"; mkdir -p "$D" && cd "$D" && tar -cf - .' > "$GECICI/uploads.tar"
[ -s "$GECICI/uploads.tar" ] || { echo "HATA: uploads.tar boş." >&2; exit 1; }
tar -tf "$GECICI/uploads.tar" >/dev/null
DOSYA_SAYISI="$(tar -tf "$GECICI/uploads.tar" | grep -vc '/$' || true)"

echo "Manifest hazırlanıyor..."
sha() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }
BACKEND_ID="$(dc ps -q backend | head -n1)"
PROJE="$(docker inspect --format '{{ index .Config.Labels "com.docker.compose.project" }}' "$BACKEND_ID" 2>/dev/null || true)"
IMAJ="$(docker inspect --format '{{.Config.Image}}' "$BACKEND_ID" 2>/dev/null || true)"
SURUM="$(dc exec -T backend sh -c 'printf %s "${APP_SURUM:-}"' 2>/dev/null || true)"
ALEMBIC="$(psql_sorgu 'select version_num from alembic_version' | head -n1)"
[ -n "$ALEMBIC" ] || { echo "HATA: alembic revizyonu okunamadı." >&2; exit 1; }

TABLOLAR="ogrenci kullanici iletisim_kisisi grup ders_oturumu yoklama ders_hakki_hareketi ogrenci_paketi odeme bildirim denetim_kaydi"
SAYIMLAR=""
for T in $TABLOLAR; do
  VAR="$(psql_sorgu "select to_regclass('public.$T') is not null")"
  if [ "$VAR" = "t" ]; then S="$(psql_sorgu "select count(*) from \"$T\"")"; else S="null"; fi
  SAYIMLAR="$SAYIMLAR    \"$T\": $S,"$'\n'
done
SAYIMLAR="${SAYIMLAR%,$'\n'}"

cat > "$GECICI/manifest.json" <<MANIFEST
{
  "zaman_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "zaman_yerel": "$(date +%Y-%m-%dT%H:%M:%S%z)",
  "compose_proje": "$PROJE",
  "backend_imaj": "$IMAJ",
  "app_surum": "$SURUM",
  "alembic_revizyon": "$ALEMBIC",
  "yukleme_dosya_sayisi": $DOSYA_SAYISI,
  "sha256_rota_dump": "$(sha "$GECICI/rota.dump")",
  "sha256_uploads_tar": "$(sha "$GECICI/uploads.tar")",
  "tablo_sayilari": {
$SAYIMLAR
  }
}
MANIFEST

echo "Şifreleniyor..."
tar -C "$GECICI" -cf - rota.dump uploads.tar manifest.json | age -R "$YEDEK_ALICI" -o "$PARCA"
[ -s "$PARCA" ] || { echo "HATA: şifreli dosya boş." >&2; exit 1; }
chmod 600 "$PARCA"
mv "$PARCA" "$HEDEF"

# Saklama süresi dolan eski yedekleri sil.
find "$YEDEK_DIZINI" -maxdepth 1 -type f -name 'rota-*.tar.age' -mtime "+$SAKLAMA_GUN" -delete

BOYUT="$(du -h "$HEDEF" | cut -f1)"
echo "Yedek hazır: $HEDEF ($BOYUT)"
