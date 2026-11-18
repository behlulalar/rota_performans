# Canlı dağıtım (ayrılmış sunucu)

Sunucu: Ubuntu 24.04, 4 vCPU / 6 GB, yalnız bu proje. Adres: `https://rotaperformans.com` (`www` çıplak alan adına yönlenir).
Compose projesi `rota-canli`. Demo dağıtımının (`deploy/demo/`) kanıtlanmış düzeninin aynısıdır.

- Dışarıya yalnız `127.0.0.1:18500` açılır. Docker, yayımlanan portlarda UFW'yi atlar; bu yüzden başka port yayımlanmaz.
  Veritabanı, Redis ve Evolution yalnız iç ağdadır. UFW yalnız 22/80/443'e izin verir.
- `ENV=production`: `/api/docs` kapalı, çerezler güvenli, örnek veri ve e2e tohum komutları reddedilir.
- Arka uç 2 işçi süreciyle çalışır (`--workers 2`); arka plan döngüleri ayrı `isci` kapsayıcısındadır.
- Bellek sınırları: db 1g, arka uç 768m, işçi 384m, Evolution 768m, redis 128m, web 64m (toplam ≈ 3,1 GB).
- **WhatsApp koruması:** `env-uret.sh` ya `--izinli +90...` (yalnız o numaraya gider) ya `--izinsiz` (gerçek velilere gider) ister.

## Kurulum
1. DNS: `@` ve `www` için A kaydı, sunucu IP'sine.
2. Kodu yerleştir (yerel makineden):
   `git archive HEAD | ssh rota 'mkdir -p /opt/rota && tar -x -C /opt/rota'`
3. Sunucuda: `cd /opt/rota/deploy/canli && bash env-uret.sh --izinli +90XXXXXXXXXX`
   (ilk denemede kendi numaranız; gerçek yayında `--izinsiz`). Yedek geri yüklenecekse eski kimlik anahtarlarını
   ortamdan verin: `KIMLIK_SIFRELEME_ANAHTARI=... KIMLIK_OZET_ANAHTARI=... bash env-uret.sh --izinsiz`.
   `.env` dosyasının yedeğini güvenli bir yere alın (anahtar kaybolursa T.C. numaraları okunamaz).
4. `docker compose build && docker compose up -d` (geçişler arka uç açılırken kendiliğinden çalışır).
5. Nginx: `mkdir -p /var/www/rota-acme`; `nginx-rota.conf` dosyasını `/etc/nginx/sites-available/rotaperformans.com` olarak
   kopyalayıp `sites-enabled`'a bağla, **önce yalnız 80 bloğu** açık kalsın (443 blokları yorum satırı), `nginx -t && systemctl reload nginx`.
6. Sertifika: `certbot certonly --webroot -w /var/www/rota-acme -d rotaperformans.com -d www.rotaperformans.com`
7. 443 bloklarını aç, `nginx -t && systemctl reload nginx`.
8. Yönetici: `docker compose exec backend python -m app.cli admin-olustur <telefon>`
9. VAPID: `docker compose exec backend python -m app.cli vapid-uret` çıktısını `.env`'e yaz, `docker compose up -d`.
10. WhatsApp: yönetici olarak WhatsApp sayfasından QR ile numarayı bağla.
11. Yedek zamanlayıcısı: `deploy/yedek/README.md` içindeki adımları uygula.

## Kurulum sonrası kontrol
Sunucu dışından (kendi bilgisayarınızdan) port taraması: `nmap -Pn -p- <sunucu-ip>` yalnız **22, 80, 443** göstermelidir.
18500, 5432, 6379, 8080 görünüyorsa dağıtımı durdurup compose `ports` ayarını düzeltin. Ayrıca
`curl -sI https://rotaperformans.com/api/docs` 404 vermeli, `http://` adresi `https://`'e yönlenmelidir.

## Güncelleme
Yerelden: `git archive HEAD | ssh rota 'tar -x -C /opt/rota'`, sonra sunucuda
`cd /opt/rota/deploy/canli && docker compose build && docker compose up -d`.
(`.env` arşivde olmadığından korunur. Güncellemeden önce yedeğin güncel olduğunu doğrulayın.)
