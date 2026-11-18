#!/usr/bin/env bash
# Rota Performans: şifreli yedek paketinden sistemi sıfırdan kurar.
# shellcheck disable=SC2016  # tek tırnaklı sh -c ifadeleri bilerek konteyner içinde açılır
# Kullanım:  bash geri-yukle.sh <yedek.tar.age> <age-kimlik-dosyasi> <compose-dizini> [--zorla]
# Ön koşul: compose dizininde .env (aynı KIMLIK_* anahtarlarıyla) var ve imajlar derlenmiş (docker compose build).
set -euo pipefail
umask 077

YEDEK="${1:-}"; KIMLIK="${2:-}"; COMPOSE_DIZINI="${3:-}"; ZORLA="${4:-}"
[ -n "$YEDEK" ] && [ -n "$KIMLIK" ] && [ -n "$COMPOSE_DIZINI" ] || {
  echo "Kullanım: bash geri-yukle.sh <yedek.tar.age> <age-kimlik-dosyasi> <compose-dizini> [--zorla]" >&2; exit 1; }
[ -z "$ZORLA" ] || [ "$ZORLA" = "--zorla" ] || { echo "HATA: bilinmeyen seçenek: $ZORLA" >&2; exit 1; }

[ -f "$YEDEK" ] || { echo "HATA: yedek dosyası yok: $YEDEK" >&2; exit 1; }
[ -f "$KIMLIK" ] || { echo "HATA: age kimlik dosyası yok: $KIMLIK" >&2; exit 1; }
[ -f "$COMPOSE_DIZINI/docker-compose.yml" ] || { echo "HATA: $COMPOSE_DIZINI/docker-compose.yml yok." >&2; exit 1; }
[ -f "$COMPOSE_DIZINI/.env" ] || { echo "HATA: $COMPOSE_DIZINI/.env yok (aynı KIMLIK_* anahtarlarıyla hazırlayın)." >&2; exit 1; }
for A in KIMLIK_SIFRELEME_ANAHTARI KIMLIK_OZET_ANAHTARI; do
  D="$(grep -E "^$A=" "$COMPOSE_DIZINI/.env" | tail -n1 | cut -d= -f2- || true)"
  [ -n "$D" ] || { echo "HATA: .env içinde $A boş veya yok." >&2; exit 1; }
done
command -v age >/dev/null || { echo "HATA: 'age' kurulu değil (apt install age)." >&2; exit 1; }

GECICI="$(mktemp -d)"
trap 'rm -rf "$GECICI"' EXIT

echo "Yedek çözülüyor..."
age -d -i "$KIMLIK" "$YEDEK" | tar -C "$GECICI" -xf -
for F in rota.dump uploads.tar manifest.json; do
  [ -s "$GECICI/$F" ] || { echo "HATA: pakette $F yok veya boş." >&2; exit 1; }
done

sha() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }
mf() { sed -n "s/^ *\"$1\": *\"\{0,1\}\([^\",]*\)\"\{0,1\},\{0,1\}$/\1/p" "$GECICI/manifest.json" | head -n1; }
[ "$(sha "$GECICI/rota.dump")" = "$(mf sha256_rota_dump)" ] || { echo "HATA: rota.dump sha256 uyuşmuyor; yedek bozuk." >&2; exit 1; }
[ "$(sha "$GECICI/uploads.tar")" = "$(mf sha256_uploads_tar)" ] || { echo "HATA: uploads.tar sha256 uyuşmuyor; yedek bozuk." >&2; exit 1; }
echo "Bütünlük doğrulandı (yedek zamanı: $(mf zaman_yerel), revizyon: $(mf alembic_revizyon))."

cd "$COMPOSE_DIZINI"
dc() { docker compose "$@"; }
psql_sorgu() { dc exec -T db psql -U rota -d rota -At -c "$1"; }

echo "db ve redis başlatılıyor..."
dc up -d --wait db redis

# Hedef şema boş olmalı: tablo varsa (öğrenci olmasa bile) geri yükleme çakışır.
TABLO="$(psql_sorgu "select count(*) from information_schema.tables where table_schema='public'")"
if [ "$TABLO" -gt 0 ] && [ "$ZORLA" != "--zorla" ]; then
  MEVCUT=0
  [ "$(psql_sorgu "select to_regclass('public.ogrenci') is not null")" = "t" ] && MEVCUT="$(psql_sorgu 'select count(*) from ogrenci')"
  echo "HATA: hedef veritabanı boş değil ($TABLO tablo, $MEVCUT öğrenci). Üzerine yazmak için --zorla ekleyin." >&2
  exit 1
fi
if [ "$ZORLA" = "--zorla" ]; then
  echo "UYARI: --zorla verildi; rota veritabanındaki public şeması SİLİNİP yeniden oluşturulacak!" >&2
  sleep 5
  dc stop backend isci web >/dev/null 2>&1 || true
  psql_sorgu 'drop schema public cascade; create schema public;' >/dev/null
fi

echo "Veritabanı geri yükleniyor..."
dc exec -T db pg_restore --no-owner --role=rota --exit-on-error -U rota -d rota < "$GECICI/rota.dump"

echo "Yüklenen dosyalar geri yükleniyor..."
if ! dc run --rm --no-deps -T --entrypoint sh backend -c 'true' >/dev/null 2>&1; then
  echo "HATA: backend imajı yok. Önce 'docker compose build' çalıştırın, sonra tekrar deneyin." >&2
  exit 1
fi
dc run --rm --no-deps -T --entrypoint sh backend -c 'D="${DOSYA_DIZINI:-/app/uploads}"; mkdir -p "$D" && tar -C "$D" -xf -' < "$GECICI/uploads.tar"

echo "backend ve web başlatılıyor (isci DEĞİL)..."
dc up -d --wait --no-deps backend
dc up -d web

echo "Doğrulama:"
HATA=0
printf '%-22s | %-8s | %-13s | %s\n' tablo yedekte "geri yuklenen" durum
for T in ogrenci kullanici iletisim_kisisi grup ders_oturumu yoklama ders_hakki_hareketi ogrenci_paketi odeme bildirim denetim_kaydi; do
  Y="$(mf "$T")"
  if [ "$(psql_sorgu "select to_regclass('public.$T') is not null")" = "t" ]; then
    G="$(psql_sorgu "select count(*) from \"$T\"")"
  else
    G="null"
  fi
  if [ "$Y" = "$G" ]; then DURUM="tamam"; else DURUM="UYUSMUYOR"; HATA=1; fi
  printf '%-22s | %-8s | %-13s | %s\n' "$T" "$Y" "$G" "$DURUM"
done
GD="$(dc exec -T backend sh -c 'D="${DOSYA_DIZINI:-/app/uploads}"; find "$D" -type f | wc -l' | tr -d '[:space:]')"
YD="$(mf yukleme_dosya_sayisi)"
if [ "$YD" = "$GD" ]; then DURUM="tamam"; else DURUM="UYUSMUYOR"; HATA=1; fi
printf '%-22s | %-8s | %-13s | %s\n' "yuklenen dosya" "$YD" "$GD" "$DURUM"

if [ "$HATA" -ne 0 ]; then echo "HATA: geri yükleme doğrulaması başarısız." >&2; exit 1; fi
echo
echo "Geri yükleme tamam. 'isci' bilerek BAŞLATILMADI (bildirim gönderir)."
echo "Kontrollerden sonra başlatın:  docker compose up -d isci evolution"
