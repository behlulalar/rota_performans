# Rota Performans Akademi: Faz Planı ve Teknik Kararlar

Paket: Önerilen (48.000 TL): temel paket + PWA/push. Performans modülü **kapsam dışı**.
Hedef teslim: Kasım 2026 son haftası. Ön ödeme: 15 Kasım. Başlangıç: müşteri bilgileri geldikten sonra.

## 1. Teknik yığın

| Katman | Seçim | Gerekçe |
|---|---|---|
| Backend | Python 3.12 + FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 | Hâkim olunan dil, tip güvenli, otomatik OpenAPI |
| Veritabanı | PostgreSQL 16 | Seçildi. İşlem bütünlüğü ders hakkı kayıtları için kritik |
| Arka plan işleri | Redis + ARQ (veya Celery) | WhatsApp/push kuyruğu, hız sınırı, tekrar deneme |
| Frontend | Vite + React (TypeScript) + Tailwind + shadcn/ui | Giriş arkasında çalışan panel: SEO/SSR gerekmez. Statik dosya olarak Caddy sunar, ek Node sunucusu yok |
| PWA / Push | Web Push (VAPID) + service worker | iOS'ta yalnızca ana ekrana eklenince çalışır (iOS 16.4+) |
| WhatsApp | Evolution API (Docker) | Karar verildi. Ban koruması aşağıda |
| Dağıtım | Docker Compose + Caddy (otomatik HTTPS) tek VPS | Bu ölçek için yeterli ve ucuz |
| Kimlik doğrulama | JWT (kısa ömürlü access + refresh), argon2 şifre özeti | Rol: admin, antrenör, veli |

**Ölçek notu:** 400+ aktif öğrenci ve ~1000 kullanıcı bir PostgreSQL + FastAPI için çok küçük bir yüktür. Asıl risk eşzamanlı kullanıcı değil, **sabah yoklama saatlerinde ani yük** ve **toplu bildirim gönderimidir**. Bunun için: indeksli sorgular, sayfalama, bildirimlerin kuyruğa alınması, bağlantı havuzu ve ders hakkı için yarış durumu (race condition) korumasından oluşan bir tasarım yeterlidir. Gereksiz mikroservis kurmayacağız.

## 2. Kritik tasarım kararları

1. **Ders hakkı = defter (ledger).** Bakiye tek bir sayı olarak tutulmaz. Her değişiklik bir hareket kaydıdır (kim, ne zaman, neden). Böylece "düzeltmeleri izleyebilme" şartı doğal olarak karşılanır.
   - Aylık paket: +8 ders (ay başı)
   - Gelmedi: telafi hakkı +1 (ayrı sayaç: `telafi`)
   - Telafi dersine katılım: telafi −1
   - Devir ve manuel düzeltme: ayrı hareket türleri
2. **Rol bazlı yetki** her uç noktada sunucu tarafında zorunlu. Veli yalnızca kendi öğrencilerinin verisine erişir.
3. **Bildirimler olay + kuyruk.** Yoklama kaydedilince doğrudan gönderilmez. Önce kuyruğa alınır, kısa bir geri alma penceresi (ör. 2–5 dk) tanınır. Yanlış "gelmedi" işaretinde veliye hatalı mesaj gitmez.
4. **WhatsApp ban koruması (Evolution API):** yalnızca izin vermiş velilere gönderim, mesaj arası rastgele gecikme, dakika/saat başına limit, mesaj şablonlarında çeşitlilik, kuyrukta tekrar deneme ve devre kesici (hata artarsa dur), bağlantı durumu izleme, yedek numara ile hızlı geçiş.
5. **KVKK:** Çocuk verisi. Aydınlatma metni, veli onayı alanı, erişim kaydı, yedekleme, silme/anonimleştirme yolu.

## 3. Fazlar

Gerçekçi not: Teklifte süre 3–5 hafta. 15 Kasım ön ödeme ile Kasım sonu arasında ~2 hafta var. Bu yüzden **Faz 0'ı ön ödemeden önce, müşteriden bağımsız işlerle yapıyoruz.** (Ön ödemeden önce çalışmaya başlamak sizin ticari kararınızdır.) Aşağıdaki program sıkıdır ve müşteri bilgilerinin geç gelmesi doğrudan teslimi kaydırır.

### Faz 0: Hazırlık ve temel (23 Eki – 14 Kas)
- Müşteri bilgi listesini gönder (`musteri-bilgi-listesi.md`)
- Domain (rotaperformans.com) ve hosting seçimi/satın alma
- Repo, Docker Compose, PostgreSQL, Alembic, CI, staging ortamı
- Tasarım sistemi: koyu tema, altın sarısı / siyah / beyaz
- Kimlik doğrulama, roller, şifre sıfırlama (e-posta/SMTP seçimi)
- Veritabanı şeması: **müşteri cevapları ve Excel dosyası gelmeden kilitlenmez.** Önce taslak, müşteri verisiyle doğrulanınca v1
- Güvenlik temelleri: yetki kontrolü, yönetici 2FA, hız sınırı, audit log (bkz. [guvenlik-plani.md](guvenlik-plani.md))
- Evolution API kurulumu ve test numarası ile deneme
- **Çıktı:** giriş yapılabilen iskelet, yayına hazır altyapı

### Faz 1: Yönetim çekirdeği (16 – 20 Kas)
- Öğrenci, veli, antrenör, grup CRUD; pasife alma
- Veli–öğrenci çoklu ilişki (bir veli, birden çok çocuk)
- Excel içe aktarma (müşteri dosyası gelince eşleme)
- Genel bakış ekranı
- **Çıktı:** yönetici gerçek veriyle öğrenci/grup yönetebilir

### Faz 2: Program, yoklama ve ders hakkı (19 – 24 Kas)
- Haftalık program ve kontenjan
- Antrenör takvimi: derse tıkla → öğrenci listesi → yoklama
- Ders hakkı defteri: aylık 8 ders, telafi sayacı, devir, düzeltme geçmişi
- Telafi dersi planlama ve düşme mantığı
- **Çıktı:** uçtan uca yoklama → ders hakkı akışı

### Faz 3: Aidat ve veli paneli (22 – 26 Kas)
- Aylık aidat, manuel ödeme girişi, ödendi/bekliyor, ödeme geçmişi
- Veli paneli: çocuklar, program, ödemeler, kalan/telafi/devreden ders
- Profil güncelleme, şifre değiştirme

### Faz 4: Bildirimler (24 – 28 Kas)
- Web Push (VAPID), cihaz kaydı, bildirim ayarları
- WhatsApp kuyruğu, ban korumaları, geri alma penceresi
- PWA kurulumu (manifest, simge, ana ekrana ekleme yönlendirmesi)

### Faz 5: Test, güvenlik ve yayına alma (27 Kas – 30 Kas)
- Yetki testleri, yük denemesi (ör. 300 eşzamanlı kullanıcı)
- iOS/Android cihaz testleri
- Şifreli yedekleme ve geri yükleme testi, izleme, KVKK metinleri
- Güvenlik kontrol listesi turu ve olay müdahale planı ([guvenlik-plani.md](guvenlik-plani.md) bölüm 8–9)
- Canlıya alma, veri aktarımı, yönetici ve antrenör eğitimi
- 1 yıllık ücretsiz bakım ve barındırma süresi başlar

## 4. Test stratejisi (Faz 0'dan itibaren, projeyi inşa ederken)

Canlı veritabanına yazan test **çalıştırılmaz.** Üç katman:

| Katman | Nerede | Ne yapar | Ne zaman |
|---|---|---|---|
| 1. Birim ve yetki testleri | CI | Ders hakkı defteri, yetki sınırları (veli/antrenör/yönetici) | Her push |
| 2. Tam E2E (Playwright) | GitHub Actions içinde geçici ortam (boş DB + sentetik veri, WhatsApp/push sahte) | Giriş, yoklama → ders hakkı → bildirim, veli paneli, telafi akışı | Her PR ve her birleştirme |
| 3. Dağıtım sonrası duman testi | Canlı | Salt okunur kontroller + işaretli test hesabı. Mesaj gönderimi kapalı | Her canlı dağıtımdan sonra, başarısızsa uyarı/geri alma |

Kurallar: gerçek öğrenci verisiyle test yok, test kayıtları `is_synthetic` ile işaretli ve raporlardan hariç, test hesaplarının sırları GitHub Secrets'ta, WhatsApp/push gönderimi test hesaplarında gerçek numaraya gitmez.

## 5. Ticari anlaşma (sözlü, yazılı teyit edilmeli)
- Fiyat: 45.000 TL, KDV/fatura yok. Ön ödeme 15 Kasım.
- Dahil: geliştirme, domain, VDS/hosting ve sistem barındırma 1 yıl.
- Bakım: ilk yıl ücretsiz. Kapsam hata düzeltme ve temel teknik destek. Yeni özellik ücretli.
- WhatsApp SIM kart, numara ve olası yenileme maliyeti müşteriye ait.
- 2. yıl hosting ve bakım ücreti: henüz belirlenmedi (PDF referansı: 1.500 TL/ay veya 15.000 TL/yıl).

## 6. Kapsam dışı
Online kart ödemesi, e-fatura/muhasebe, mağaza uygulaması, performans modülü, yeni özellikler.
