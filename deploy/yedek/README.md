# Rota Performans: şifreli yedek ve geri yükleme

## Pakette ne var, ne yok
Tek dosya: `rota-YYYYmmdd-HHMMSS.tar.age` (içinde `rota.dump`, `uploads.tar`, `manifest.json`).
- VAR: `rota` veritabanı (pg_dump), yüklenen dosyalar (fotoğraflar), manifest (sürüm, alembic revizyonu, tablo satır sayıları, sha256).
- YOK: `evolution` veritabanı (WhatsApp oturumu yeniden eşleştirilir), redis (geçici veri), `.env` sırları.
- `.env` (özellikle `KIMLIK_SIFRELEME_ANAHTARI` ve `KIMLIK_OZET_ANAHTARI`) ayrıca saklanır. Bu anahtarlar olmadan kimlik verileri çözülemez.

## Anahtar yönetimi
1. Kendi bilgisayarınızda: `age-keygen -o rota-yedek-anahtar.txt`
2. Çıktıdaki yalnız genel `age1...` satırını sunucuda `/etc/rota/yedek-alici.txt` dosyasına yazın.
3. `rota-yedek-anahtar.txt` (özel anahtar) parola yöneticisinde durur; sunucuya ASLA konmaz. Yalnız geri yüklerken verilir.

## Elle yedek
    sudo YEDEK_DIZINI=/var/backups/rota bash /opt/rota/deploy/yedek/yedek-al.sh /opt/rota/deploy/canli
Ortam değişkenleri: `YEDEK_DIZINI` (varsayılan /var/backups/rota), `YEDEK_ALICI` (/etc/rota/yedek-alici.txt), `SAKLAMA_GUN` (14).

## Geri yükleme (yeni sunucu)
1. `age` ve docker kurulu olsun; depo `/opt/rota` altında; compose dizininde `.env` hazır (aynı KIMLIK_* anahtarlarıyla).
2. `docker compose build` (imajlar yoksa betik uyarır ve durur).
3. Yedek dosyasını ve özel anahtarı geçici olarak sunucuya alın, sonra:

       bash geri-yukle.sh <yedek.tar.age> <anahtar.txt> <compose-dizini>
   Hedefte öğrenci kaydı varsa durur; bilerek silmek için sonuna `--zorla` ekleyin.
4. Betik sha256 doğrular, tablo sayılarını yedekle karşılaştırır. `isci` bilerek başlatılmaz (bildirim gönderir). Kontrollerden sonra: `docker compose up -d isci evolution`
5. Özel anahtarı sunucudan silin.

## systemd kurulumu
    sudo cp /opt/rota/deploy/yedek/rota-yedek.{service,timer} /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now rota-yedek.timer
    systemctl list-timers rota-yedek.timer
    sudo systemctl start rota-yedek.service   # deneme

## Sonraki adım
Sunucu dışı kopya (rclone ile Google Drive) henüz yok; ayrı bir adım olarak eklenecek.
