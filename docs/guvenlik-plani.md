# Rota Performans Akademi: Güvenlik Planı

Sistem yaklaşık 400 öğrencinin (çoğu 18 yaş altı) ve velilerinin kişisel verisini barındıracak. Bu plan, sözleşmenin Madde 10.5'inde taahhüt edilen tedbirleri ve ötesini kapsar. **Sözleşmede yazılan her tedbir fiilen uygulanmalıdır.** Tedbirlerin bir kısmı "S" ile işaretlidir; bunlar sözleşmede açıkça taahhüt edilmiştir.

Öncelik: **P0** = canlıya almadan önce şart, **P1** = canlıdan sonraki ilk 2 hafta içinde, **P2** = iyileştirme.
Faz: [faz-plani.md](faz-plani.md) içindeki faz numarası.

## 1. Tehdit özeti (neye karşı korunuyoruz)

| Tehdit | Örnek |
|---|---|
| Yetki aşımı (IDOR) | Bir velinin, URL'deki öğrenci kimliğini değiştirip başkasının çocuğunun verisini görmesi |
| Hesap ele geçirme | Zayıf/çalıntı veli şifresi, yönetici hesabının ele geçirilmesi |
| Açık servis | İnternete açık PostgreSQL, Redis veya Evolution API |
| Veri sızıntısı | Şifresiz yedek, loglarda kişisel veri, Excel dosyasının dolaşması |
| Uygulama açıkları | SQL injection, XSS, CSRF, kötü niyetli dosya yükleme |
| WhatsApp oturumu çalınması | Evolution API oturum bilgilerinin ele geçirilmesi |

## 2. Uygulama güvenliği

| # | Tedbir | Öncelik | Faz | S |
|---|---|---|---|---|
| A1 | **Her uç noktada sunucu tarafı yetki kontrolü.** Veli yalnızca kendi öğrencilerini, antrenör yalnızca kendi gruplarını görür | P0 | 0–3 | S |
| A2 | **Yetki testleri otomatik:** "veli A, veli B'nin çocuğuna erişemez", "antrenör başka grubun yoklamasını göremez" gibi testler CI'da çalışır | P0 | 0–5 | |
| A3 | **Yönetici hesabında zorunlu 2 adımlı doğrulama (TOTP)** | P0 | 0 | |
| A4 | Şifre özetleme: argon2. Minimum uzunluk, yaygın şifre kontrolü | P0 | 0 | S |
| A5 | Giriş ve şifre sıfırlamada hız sınırı, art arda başarısız denemede geçici kilit | P0 | 0 | |
| A6 | Şifre sıfırlama: tek kullanımlık, kısa ömürlü (ör. 30 dk) bağlantı. Hesap varlığını sızdıran mesaj yok | P0 | 0 | |
| A7 | Oturum: kısa ömürlü access token + dönen refresh token. Çıkışta ve şifre değişiminde iptal | P0 | 0 | |
| A8 | Sıralı sayı yerine UUID kimlikler | P0 | 0 | |
| A9 | Girdi doğrulama (Pydantic), yalnızca parametreli sorgular (ORM) | P0 | 0–4 | |
| A10 | Sıkı CORS, güvenlik başlıkları (HSTS, CSP, X-Content-Type-Options, frame koruması) | P0 | 0 | |
| A11 | Excel içe aktarma yalnızca yöneticide: dosya türü/boyut sınırı, formül ve makro çalıştırılmaz | P0 | 1 | |
| A12 | Veli hesabı açılışı: yönetici davet bağlantısı oluşturur, geçici şifre düz metin olarak saklanmaz | P0 | 3 | |
| A13 | Hata mesajlarında iç ayrıntı (stack trace, SQL) kullanıcıya gösterilmez | P0 | 0 | |
| A14 | Yönetici dışındaki roller için de isteğe bağlı 2FA | P2 | sonra | |

## 3. Sunucu ve altyapı

| # | Tedbir | Öncelik | Faz | S |
|---|---|---|---|---|
| S1 | Güvenlik duvarı: yalnızca 80/443 ve SSH açık | P0 | 0 | |
| S2 | **PostgreSQL, Redis, Evolution API internete kapalı**, yalnızca Docker iç ağında. Evolution yönetim arayüzü dışarı açık değil | P0 | 0 | S |
| S3 | SSH yalnızca anahtarla, root girişi kapalı, fail2ban | P0 | 0 | |
| S4 | Otomatik güvenlik güncellemeleri (unattended-upgrades) | P0 | 0 | S |
| S5 | HTTPS her yerde (Caddy otomatik sertifika), HTTP'den yönlendirme | P0 | 0 | S |
| S6 | Sırlar (.env, API anahtarları) kod deposuna girmez. `.gitignore`, ortam başına ayrı değerler | P0 | 0 | |
| S7 | Konteynerler root olmayan kullanıcıyla çalışır. Gereksiz paket ve port yok | P1 | 0–5 | |
| S8 | Bu sunucu diğer projelerden **ayrı** | P0 | 0 | |
| S9 | Veritabanı kullanıcısı en az yetkiyle (uygulama kullanıcısı şema değiştiremez) | P1 | 0 | |
| S10 | Çalışma durumu ve disk/bellek izleme, art arda başarısız giriş uyarısı | P1 | 5 | |

## 4. Veri koruma

| # | Tedbir | Öncelik | Faz | S |
|---|---|---|---|---|
| V1 | **Veri minimizasyonu:** Sağlık bilgisi toplanmaz. T.C. kimlik no ve fotoğraf müşteri talebiyle toplanır, her alanın neden toplandığı yazılı olur. Gereksiz hiçbir alan eklenmez | P0 | 0–1 | S |
| V2 | **Şifreli yedek**, günlük, sunucudan ayrı yerde, en az 14 gün saklanır | P0 | 5 | S |
| V3 | Yedekten geri yükleme **gerçekten denenir** (en az 1 kez canlıya almadan önce) | P0 | 5 | |
| V4 | **İşlem kaydı (audit log):** kim, neyi, ne zaman değiştirdi (ders hakkı düzeltmesi, silme, yönetici işlemleri, veri dışa aktarım) | P0 | 0–3 | S |
| V5 | Loglara kişisel veri, şifre ve token yazılmaz | P0 | 0 | |
| V6 | **Geliştirme ve test ortamında gerçek veri yok**, sahte (anonim) veri kullanılır | P0 | 0 | S |
| V7 | Müşterinin Excel dosyası: güvenli kanaldan alınır, içe aktarıldıktan sonra geliştirici bilgisayarından ve sohbetlerden silinir | P0 | 1 | |
| V8 | Silme/anonimleştirme yolu: pasif öğrenci ve sözleşme sonu verisi için | P1 | 3–5 | S |
| V9 | Yönetici için tüm veriyi dışa aktarma (Excel/CSV), erişimi kayıt altında | P1 | 3 | S |
| V10 | **T.C. kimlik no alan düzeyinde şifreli saklanır** (anahtar veritabanından ayrı tutulur). Listelerde maskeli gösterilir, tam değer yalnızca yetkili yönetici ekranında ve erişim kayıt altında | P0 | 0–1 | S |
| V11 | **Fotoğraflar herkese açık adreste değil**, özel depolamada. Yalnızca giriş yapmış kullanıcıya, kimlik doğrulamalı API ucundan sunulur (`Cache-Control: private, no-cache` + ETag); imzalı/süreli bağlantı kullanılmaz. Yüklemede tür/boyut kontrolü, EXIF/konum bilgisi silinir, yeniden boyutlandırılır | P0 | 1 | S |
| V12 | Fotoğraf için **veli açık rızası ayrı alan** olarak tutulur. Rıza geri çekilirse fotoğraf silinir. Sosyal medya/tanıtım kullanımı bu sistemin dışında, ayrı izinle. Antrenör fotoğraf rızası `antrenor_foto_rizasi` tablosunda tutulur; yükleme aktif rıza ister, geri çekilince fotoğraf silinir, işlem denetim kaydına yazılır. (Antrenör tarafı plan yazıldıktan sonra eklendi, Kasım 2026; ayrıca değişebilir) | P0 | 1 | |
| V13 | Fotoğraflar ve T.C. no şifreli yedeklere dahil. Test ve geliştirme ortamlarında **gerçek fotoğraf ve kimlik no yok** | P0 | 5 | S |

## 5. WhatsApp ve bildirimler

| # | Tedbir | Öncelik | Faz |
|---|---|---|---|
| W1 | Evolution API anahtarı ve webhook gizli anahtarı. Yönetim arayüzü dışarı kapalı | P0 | 0 |
| W2 | Oturum bilgisi ve veritabanı yedeği şifreli, erişim kısıtlı | P0 | 4 |
| W3 | Yalnızca bildirim iznini vermiş velilere gönderim. Mesaj reklam/pazarlama için kullanılamaz | P0 | 4 |
| W4 | Mesajlarda gereksiz kişisel veri yok (örn. yalnızca öğrenci adı ve ders bilgisi) | P0 | 4 |
| W5 | Push: VAPID özel anahtarı korunur, abonelikler çıkışta ve hesap silinince silinir | P0 | 4 |
| W6 | Ban/oturum kopma durumunda yönetici uyarısı | P1 | 4 |

## 6. Süreç ve geliştirme

| # | Tedbir | Öncelik | Faz |
|---|---|---|---|
| G1 | Bağımlılık taraması (`pip-audit`, `npm audit`), açık bulunan paketlerin güncellenmesi | P1 | 0–5 |
| G2 | Kod gözden geçirme: her yetki ve veri erişim değişikliğinde kontrol listesi | P1 | 0–5 |
| G3 | Canlıya almadan önce OWASP Top 10 kontrol listesi turu | P0 | 5 |
| G4 | Dağıtım betiği: sunucu sıfırdan kurulabilir (taşınabilirlik ve felaket kurtarma) | P1 | 5 |
| G5 | Olay müdahale planı (aşağıda) | P0 | 5 |

## 7. KVKK (müşteriyle birlikte)

- **Aydınlatma metni** ve **veli açık rızası** (çocuk verisi için veli/vasi). Sistemde onay alanı ve onay tarihi tutulur.
- WhatsApp ve telefon bildirimi için ayrı izin.
- **VERBİS** kaydı gerekip gerekmediğini müşteri kendi durumuna göre kontrol eder. Bunu biz teyit etmiyoruz.
- Saklama süresi: aktif ve pasif öğrenci için müşteri karar verir (bilgi listesi madde 28).
- İlgili kişi başvuruları (erişim, düzeltme, silme) için yönetici ekranında yol.
- Çocuk verisi, sağlık bilgisi ve fotoğraf için özel dikkat. Müşteri istemezse **hiç toplamayız**.

## 8. Olay müdahale planı (kısa)

1. **Tespit:** uyarı, kullanıcı bildirimi veya anormal log.
2. **Sınırlama:** etkilenen hesapları kilitle, token'ları iptal et, gerekirse sistemi geçici kapat.
3. **BehTech → Müşteri bildirimi:** gecikmeksizin ve en geç **48 saat** içinde (sözleşme Madde 10.7). İçerik: ne oldu, hangi veri, kaç kişi, alınan tedbirler.
4. **Müşteri → Kurul ve ilgili kişiler:** Veri Sorumlusu olarak müşteri, ihlali öğrendiğinden itibaren **72 saat** içinde Kişisel Verileri Koruma Kurulu'na bildirir. Bu nedenle bizim 48 saatlik bildirimimiz müşteriye süre bırakır.
5. **Düzeltme ve inceleme:** kök neden, yama, olay raporu.
6. **Kayıt:** olay, kararlar ve tarihler saklanır.

## 9. Canlıya almadan önce kontrol listesi (Faz 5)

- [ ] DB, Redis ve Evolution portları dışarıdan kapalı (dışarıdan port taraması ile doğrulandı)
- [ ] Yönetici hesaplarında 2FA zorunlu
- [ ] Yetki testlerinin hepsi geçiyor (veli/antrenör/yönetici sınırları)
- [ ] Şifreli yedek alındı ve geri yüklendi
- [ ] Loglarda kişisel veri veya token yok
- [ ] HTTPS ve güvenlik başlıkları doğrulandı
- [ ] Sunucuda gereksiz hesap, port ve varsayılan şifre yok
- [ ] Müşteri Excel dosyası geliştirici bilgisayarından silindi
- [ ] Test ortamında gerçek veri yok
- [ ] Olay müdahale planı müşteriyle paylaşıldı

## 10. Bilinen sınırlar (dürüst not)

- Evolution API resmi olmayan bir yöntemdir. Güvenlik bakımından WhatsApp'ın kendi güvencelerine bağlıyız ve hesap kısıtlama riski vardır (sözleşme Madde 8.4).
- Bu plan bir hukuki görüş veya bağımsız sızma testi değildir. İstenirse canlıya almadan sonra bağımsız bir güvenlik incelemesi yapılabilir (kapsam dışı, ayrıca ücretlendirilir).
- Disk düzeyinde şifreleme (LUKS) VDS ortamında sağlayıcıya bağlıdır. Gerekirse yedek şifreleme ve veri minimizasyonuyla dengelenir.
