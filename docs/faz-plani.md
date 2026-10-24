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

**İlerleme takibi:** `[x]` tamamlandı, `[ ]` bekliyor. GitHub'da kutucuklar işaretli görünür. Bir iş bitince bu dosya aynı değişiklikle güncellenir.

### Faz 0: Hazırlık ve temel (23 Eki – 14 Kas)
Altyapı
- [x] Repo, Docker Compose, PostgreSQL, Redis, Alembic
- [x] Test altyapısı (ayrı test veritabanı, ders hakkı ve yetki testleri)
- [x] CI iş akışı yazıldı (backend testleri + frontend derlemesi)
- [x] Dal akışı: `ozellik/*` dalları testler geçerse otomatik `main`'e aktarılır
- [x] CI GitHub'da ilk kez yeşil çalıştı (dal akışı ile doğrulandı)
- [x] Playwright E2E: 8 tarayıcı senaryosu, ayrı veritabanı, CI'da Preview öncesi zorunlu
- [ ] Staging ortamı (VDS gelince)

Kimlik ve güvenlik
- [x] Giriş, yenileme, çıkış; rol bazlı yetki (admin, antrenör, veli, öğrenci)
- [x] Hesap kilidi, IP hız sınırı, denetim kaydı
- [x] T.C. kimlik şifreleme (AES-GCM) ve tekrar kontrolü (HMAC)
- [ ] Yönetici 2 adımlı doğrulama (TOTP)
- [ ] Şifre sıfırlama (e-posta/SMTP seçimi gerekli)

Veri
- [x] Veritabanı şeması: 19 tablo, kurallar veritabanında, testlerle kanıtlı
- [ ] Şema, müşteri cevapları ve Excel dosyasıyla doğrulanır, gerekirse güncellenir

Arayüz
- [x] Koyu tema renk paleti (altın sarısı / siyah / beyaz), giriş ve boş panel sayfası
- [ ] Bileşen kütüphanesi (shadcn/ui), her dilimde ihtiyaç oldukça eklenir

Dış işler
- [ ] Müşteri bilgi listesi müşteriye gönderildi
- [ ] Domain (rotaperformans.com) satın alındı
- [ ] VDS siparişi verildi
- [ ] Evolution API deneme kurulumu ve test numarası ile deneme

### Faz 1: Yönetim çekirdeği (16 – 20 Kas)
Her dilim bir dalda geliştirilir: backend + frontend birlikte, testler geçince `main`'e girer.

**Dilim 1.1: Öğrenci kaydı ve listesi**
- [x] Backend: öğrenci oluştur, listele, getir, güncelle, pasife al
- [x] T.C./pasaport şifreli saklama, tekrar kontrolü, 5 yaş altı uyarısı
- [x] İletişim kişileri ve birincil kişi kuralı (en az bir birincil, en az bir "diğer")
- [x] Rıza kayıtları (aydınlatma, fotoğraf, WhatsApp)
- [x] Fotoğraf yükleme (özel depolama, küçük önizleme)
- [x] Frontend: öğrenci listesi (arama, filtre, fotoğraf)
- [x] Frontend: kayıt formu

**Dilim 1.2: Antrenör ve grup yönetimi**
- [x] Antrenör ekleme (hesap oluşturma)
- [x] Grup, haftalık program slotları, kontenjan
- [x] Öğrenciyi gruba ekle/çıkar, doluluk göstergesi

**Dilim 1.3: Veli ve reşit öğrenci hesapları**
- [x] Birincil kişiye hesap açma ve giriş bilgisini iletme
- [x] Kardeşler için tek hesap
- [x] Reşit öğrenci hesabı ve 18 yaş uyarısı

**Dilim 1.4: Excel içe aktarma**
- [ ] Müşterinin Excel dosyası gelince sütun eşleme ve aktarma (önizleme + hata raporu)

**Dilim 1.5: Genel bakış ekranı**
- [x] Aktif öğrenci, grup doluluğu, bekleyen ödemeler özeti

### Faz 2: Program, yoklama ve ders hakkı (19 – 24 Kas)
- [x] Haftalık programdan tarihli ders oturumları üretme
- [x] Antrenör takvimi: derse tıkla → öğrenci listesi → yoklama (geldi/gelmedi)
- [x] Yoklama sonrası 1 saatlik gecikmeyle telafi hakkı (arka plan işi)
- [x] Ders hakkı defteri ekranı, düzeltme geçmişi, manuel düzeltme
- [x] Telafi dersi planlama ve düşme mantığı
- [x] Yönetici paneli yoklama düzeltme yetkisi
- [x] Antrenör yoklaması ders başlamadan 15 dakika önce açılır (yönetici muaf)

### Faz 3: Paket, ödeme ve veli paneli (22 – 26 Kas)
- [ ] Paket tanımları (aylık 8 ders), özel fiyat girişi
- [ ] "Ödeme alındı" işareti → ders hakkı otomatik yüklenir
- [ ] Ödeme geçmişi
- [ ] Veli paneli: çocuklar, program, ödemeler, kalan/telafi ders
- [ ] Profil güncelleme, şifre değiştirme

### Faz 4: Bildirimler (24 – 28 Kas)
- [ ] Web Push (VAPID), cihaz kaydı, bildirim ayarları
- [ ] WhatsApp kuyruğu, ban korumaları, geri alma penceresi
- [ ] Bildirimler yalnızca birincil iletişim kişisine
- [ ] PWA kurulumu (manifest, simge, ana ekrana ekleme yönlendirmesi)

### Faz 5: Test, güvenlik ve yayına alma (27 Kas – 30 Kas)
- [ ] Yetki testleri, yük denemesi (ör. 300 eşzamanlı kullanıcı)
- [ ] iOS/Android cihaz testleri
- [ ] Şifreli yedekleme ve geri yükleme testi, izleme, KVKK metinleri
- [ ] Güvenlik kontrol listesi turu ve olay müdahale planı ([guvenlik-plani.md](guvenlik-plani.md) bölüm 8–9)
- [ ] Dağıtım sonrası duman testi
- [ ] Canlıya alma, veri aktarımı, yönetici ve antrenör eğitimi
- [ ] 1 yıllık ücretsiz bakım ve barındırma süresi başlar

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
