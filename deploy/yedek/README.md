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

## Sunucu dışı kopya (Google Drive)
Her günlük yedek, istenirse rclone ile Google Drive'a da yüklenir; `DRIVE_SAKLAMA_GUN` günden eski uzak yedekler silinir. Yükleme veya boyut doğrulaması başarısızsa yerel yedek kalır, uzak temizlik yapılmaz ve servis başarısız (failed) olur. `RCLONE_HEDEF` boşsa yükleme kapalıdır.

1. Sunucuda rclone kurun: `curl https://rclone.org/install.sh | sudo bash` (veya `sudo apt install rclone`).
2. Kendi Mac'inizde yetkilendirin: `rclone authorize "drive" --drive-scope drive.file`. Tarayıcıda giriş yapınca terminale bir token (JSON) yazılır. `drive.file` kapsamında rclone yalnız kendi oluşturduğu dosyaları görür; Drive'ın geri kalanına erişemez.
3. Sunucuda `sudo rclone config`: yeni remote adı `rota-drive`, tür `drive`, scope `drive.file`, "Use auto config?" sorusuna `n`, sonra Mac'te üretilen token'ı yapıştırın.
4. `/etc/rota/yedek.env` dosyasını oluşturun ve `sudo chmod 600 /etc/rota/yedek.env` yapın:

       RCLONE_HEDEF=rota-drive:RotaYedek
       DRIVE_SAKLAMA_GUN=90
5. Deneme: `sudo systemctl start rota-yedek.service && journalctl -u rota-yedek.service -n 20` ("Drive'a gönderildi" satırını arayın).

Token bir sırdır: yalnız sunucu terminaline yapıştırın; sohbete, depoya veya e-postaya asla koymayın. rclone ayarı `/root/.config/rclone/rclone.conf` içindedir ve token'ı içerir; bu dosyayı da paylaşmayın.
