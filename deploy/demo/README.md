# Demo/test dağıtımı (tek sunucu, izole)

Amaç: ana sunucuya geçmeden önce sistemi gerçek adreste (HTTPS, push, PWA, WhatsApp) denemek.
Adres: `https://rota.behlulalar.online`. Sunucuda diğer sistemlerden bağımsız Compose projesi `rota-demo`.

- Dışarıya yalnız `127.0.0.1:18500` açılır (ön uç + `/api`). Veritabanı, Redis ve Evolution dışarıdan görünmez.
- TLS ve alan adı sunucudaki ana nginx'te; bu klasördeki `nginx-rota.conf` yeni bir site dosyası olarak eklenir.
- `ENV=demo`: örnek veri yüklenebilir, `/api/docs` kapalı, çerezler güvenli.
- **WhatsApp koruması:** `WHATSAPP_IZINLI_NUMARALAR` doluyken WhatsApp yalnız o numaralara gider. Örnek verideki
  numaralar gerçek kişilere ait olabilir; bu liste boşaltılmamalıdır.

## Kurulum (sunucuda, `/opt/rota-demo` içinde)
1. DNS: `rota.behlulalar.online` için A kaydı → sunucu IP'si.
2. Kodu yerleştir: depo klasörünü `/opt/rota-demo`'ya al (git clone ya da rsync).
3. `cd /opt/rota-demo/deploy/demo && bash env-uret.sh +905XXXXXXXXX` (WhatsApp'a izinli TEK numara).
4. `docker compose build && docker compose up -d` (geçişler arka uç açılırken kendiliğinden çalışır).
5. Nginx: `nginx-rota.conf` önce yalnız 80 bloğuyla etkinleştirilir, `certbot certonly --webroot -w /var/www/rota-acme -d rota.behlulalar.online`, sonra 443 bloğu açılır, `nginx -t && systemctl reload nginx`.
6. Yönetici: `docker compose exec backend python -m app.cli admin-olustur <telefon>`.
7. Örnek veri (isteğe bağlı): `docker compose exec backend python -m app.cli ornek-veri`.
8. VAPID: `docker compose exec backend python -m app.cli vapid-uret` çıktısını `.env`'e yaz, `docker compose up -d` ile yeniden başlat.
9. WhatsApp: yönetici olarak Ayarlar → WhatsApp bağlantısı → QR ile kendi numaranı bağla.

## Güncelleme
`git pull && cd deploy/demo && docker compose build && docker compose up -d`

## Kaldırma (testler bitince)
`cd /opt/rota-demo/deploy/demo && docker compose down -v` (verileri de siler), sonra nginx site dosyasını
`sites-enabled`'dan kaldırıp `reload`, `certbot delete --cert-name rota.behlulalar.online`, `/opt/rota-demo` silinir,
DNS kaydı kaldırılır. Diğer sistemlere dokunulmaz.

## Notlar
- `.env` depoya girmez. `KIMLIK_SIFRELEME_ANAHTARI` kaybolursa T.C. numaraları okunamaz: yedeğini alın.
- Bellek sınırları: db 512M, arka uç 512M, işçi 256M, Evolution 768M, redis 128M, web 64M (toplam ≈ 2,2 GB).
