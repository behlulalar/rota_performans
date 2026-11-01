# Bildirim kuralları ve kontroller

Velilere giden bildirimlerde uygulanan kurallar, alınan kararlar ve WhatsApp için planlanan ban koruması.
Durum: 29 Ekim 2026. Uygulama bildirimi (push) hazır; WhatsApp gönderimi Evolution API ile birlikte (Faz 4.4) yazılacak.

## 1. Genel kurallar (tüm kanallar)

| Kural | Nasıl uygulanıyor | Durum |
|---|---|---|
| Bildirim yalnızca **birincil iletişim kişisine** gider | Kuyruğa eklerken yalnız `birincil` kişi alıcı olur; birincil kişi yoksa bildirim oluşmaz | Hazır, testli |
| Kuyrukta **kişisel veri tutulmaz** | Otomatik bildirimlerde yalnız şablon adı ve kimlikler saklanır; mesaj metni gönderim anında üretilir. Duyuru metni ise kulübün kendi yazdığı metindir ve saklanır | Hazır |
| **Aynı bildirim iki kez oluşmaz** | Veritabanında tekil indeks (yoklama + kanal + şablon; duyuruda duyuru + alıcı + kanal) | Hazır |
| **Kardeşler tek bildirim alır** (duyurularda) | Aynı birincil kişiye bağlı öğrenciler birleştirilir | Duyurularla geliyor |
| Veli **kanal ve tür tercihlerini** kendisi seçer | Veli profili > Bildirimler: devamsızlık, ders hakkı hatırlatmaları, WhatsApp, uygulama bildirimi | Hazır |
| Duyurular tür tercihine takılmaz, **kanal tercihine** uyar | Ders iptali gibi duyurular "devamsızlık / ders hakkı" kapalı olsa da gider; ama veli WhatsApp'ı veya uygulama bildirimini kapattıysa o kanaldan gitmez | Duyurularla geliyor |
| Yönetici her bildirimi **izleyebilir ve müdahale edebilir** | Sistem > Bildirimler: bekleyeni iptal, hatalıyı yeniden dene; işlemler denetim kaydına yazılır | Hazır |

## 2. Otomatik bildirimler

| Olay | Ne zaman | Kontrol |
|---|---|---|
| Devamsızlık (`ders_gelmedi`) | Öğrenci "gelmedi" işaretlenince | **Geri alma penceresi:** varsayılan 3 dk bekler (Ayarlar'dan 1–15 dk). Bu sürede yoklama düzeltilirse bildirim iptal olur, hiç gitmez. Telafi derslerinde oluşmaz |
| Ders hakkı azaldı | Kalan ders eşiğe düşünce (varsayılan 2, Ayarlar'dan 1–5) | Aynı paket döneminde bir kez |
| Ders hakkı bitti | Ödenmiş paketi olan öğrencinin hakkı 0 veya altına inince | Aynı paket döneminde bir kez; yeni paket yüklenince sıfırlanır |

Bilinen sınır: yoklama düzeltilince yalnız devamsızlık bildirimi iptal edilir; kuyruğa girmiş "ders hakkı azaldı/bitti" geri alınmaz.

## 3. Uygulama bildirimi (Web Push)

- Gönderim için sunucuda **VAPID anahtarları** gerekir (`python -m app.cli vapid-uret`). Anahtar yoksa push kapalıdır, sistemin geri kalanı etkilenmez. Özel anahtar depoya yazılmaz.
- Alıcının uygulamaya giriş hesabı olmalı ve en az bir cihazda bildirimi açmış olmalı.
- Geçersiz cihaz kaydı (404/410) otomatik silinir.
- Hata alınırsa artan aralıklarla (2, 4, 8… dk) **5 kez** denenir, sonra "hatalı" olur.
- **24 saatten eski** bekleyen bildirim gönderilmez, iptal edilir (eski bir devamsızlık mesajı geç gitmesin diye).
- Bildirime dokununca uygulamada ilgili sayfa açılır.
- **Sınırı:** "Gönderildi", Apple/Google'ın bildirimi teslim aldığı anlamına gelir; velinin görüp okuduğunu göstermez. Veli telefonda bildirimi susturduysa bunu bilemeyiz.

## 4. WhatsApp — planlanan ban koruması (Faz 4.4, Evolution API ile)

Kulübe ait, kişisel kullanılmayan ayrı bir WhatsApp numarası kullanılacak.

**Bağlantı (hazır, 1 Kasım 2026):** Yönetici veya teknik destek Ayarlar > WhatsApp bağlantısı kartından QR okutarak numarayı bağlar, durumu görür ve bağlantıyı keser (denetim kaydına yazılır). Evolution API `docker-compose.yml` içinde `evolution` servisi olarak çalışır (sürüm sabit: v2.3.7, ayrı `evolution` veritabanı). Ayarlar: `EVOLUTION_URL`, `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE`. Aşağıdaki gönderim kuralları henüz yazılmadı.

**Kime:**
- Yalnız WhatsApp izni (rıza) olan birincil iletişim kişileri.
- Aynı numaraya tek mesaj (kardeşler birleşir).
- Hiç konuşulmamış numaralara toplu ilk mesaj riski: velilerden kulüp numarasını kaydetmeleri istenecek.

**Hız ve zaman:**
- Mesajlar arası rastgele 25–70 sn bekleme, öncesinde "yazıyor…" göstergesi.
- Saatlik ve günlük üst sınır (örn. 50 / 250), Ayarlar'dan değiştirilebilir.
- Yeni numara için ısınma dönemi: ilk günlerde düşük limit, kademeli artış.
- Yalnız 09:00–21:00 arası gönderim; dışında kalan ertesi sabaha kalır.

**İçerik:**
- Her mesaj birebir aynı olmaz: şablonun birkaç farklı söylenişi dönüşümlü, öğrenci adıyla.
- Link yok ya da en fazla bir tane.

**Öncelik ve güvenlik:**
- Kişisel mesajlar (devamsızlık) toplu duyurunun önüne geçer.
- **Devre kesici:** bağlantı koparsa veya art arda hata gelirse gönderim durur, yönetici ekranında uyarı çıkar.
- Hiçbir mesaj iki kez gönderilmez.
- Uygulama bildirimi ve WhatsApp ayrı izlenir (Bildirimler ekranında iki sekme, her duyuruda kanal başına sonuç).

## 5. Duyurular ve ders iptali (yönetici)

- Hedef: bir ders oturumu, seçilen gruplar veya tüm aktif öğrenciler.
- Göndermeden önce özet gösterilir (kaç veli, kaçı uygulama bildirimi alacak, kaçında kapalı) ve onay istenir.
- **Ders iptali:** yoklaması alınmış ders iptal edilemez; o derse planlanmış telafiler kaldırılır, telafi hakkı yeniden planlanabilir olur. İptalden sonra "Velilere bildirilsin mi?" sorulur. Antrenör ders iptal edemez.
- WhatsApp seçeneği Evolution API bağlanana kadar kapalıdır.

## 6. Açık kararlar

1. **Uygulama bildirimi açıksa WhatsApp gönderilmesin mi?** Ban riskini en çok azaltan seçenek, ama push'un okunduğu garanti değil (bkz. bölüm 3). Öneri: "son 30 günde başarılı bildirim almış cihazı olan" veliye WhatsApp gönderme; ders iptali gibi önemli duyurularda "her iki kanaldan gönder" seçeneği. Karar 4.4'te verilecek.
2. WhatsApp saatlik/günlük limitlerinin ve ısınma takviminin kesin değerleri, numaranın yaşına göre belirlenecek.
