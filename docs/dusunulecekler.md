# Düşünülecekler

Şimdilik kapsam dışı veya cevabı bekleyen konular. Karar verildikçe ilgili dokümana taşınır.

## 1. Birincil iletişim kişisi değişirse hesap devri
**Durum:** Düşünülecek, ilk sürümde yok.

**Sorun:** Panel hesabı yalnızca birincil kişide. Birincil kişi değişirse (boşanma, taşınma, farklı veli) hesabın kime gideceği belirsiz.

**Düşünceler**
- Yönetici, öğrencinin birincil kişisini tek işlemle değiştirebilmeli. Eski kişinin erişimi anında kapanmalı, yeni kişi için hesap açılmalı.
- Eski kişinin **geçmiş bildirimleri ve kayıtları** değişmez, denetim kaydında kalır.
- Bildirim alıcısı da yeni kişiye döner.
- Kardeşlerde aynı hesap birden çok çocuğa bağlıysa, değişiklik **tüm çocuklar için mi** yoksa **yalnızca seçilen çocuk için mi** olacağını işlem sırasında sormak gerek.
- Güvenlik: Bu işlem kötüye kullanılırsa başkası çocuğun verisine erişir. Yalnızca yönetici yapabilsin, yeni telefon doğrulanmadan hesap açılmasın, değişiklik denetim kaydına yazılsın.
- Hukuki taraf: Velayet anlaşmazlığı durumunda hangi kişinin yetkili olduğuna karar vermek kulübün sorumluluğunda. Sistem bunu kendisi yargılamaz.

**Gerekli veri:** `iletisim_kisisi` üzerinde birincil işareti değiştirme, `kullanici` bağlantısını taşıma, `denetim_kaydi` girişi. Şema bunu şimdiden karşılıyor, ek tablo gerekmez.

## 2. Telafi hakkı son kullanma süresi
**Durum:** Müşteriye sorulacak. Şimdilik süresiz.
- Şemada `son_kullanma` alanı hazır ve boş.
- Soru: telafi kaç ay içinde kullanılmalı? Süre dolunca hak yanar mı, yoksa yönetici onayıyla uzatılabilir mi?

## 3. Yoklamada ek durumlar
**Durum:** İlk aşamada yalnızca geldi/gelmedi.
- Sonra eklenecekler: mazeretli, raporlu, geç kaldı.
- Her biri telafi hakkını farklı etkileyebilir (ör. raporlu → telafi doğar mı, normal ders yanar mı).
- Müşteriden kural tablosu istenecek. Yoklama durumu bir listeden seçildiği için şema genişletmeye açık.

## 4. 18 yaş geçişinin otomasyonu
**Durum:** İlk sürümde yönetici onaylı.
- Daha sonra tam otomatik yapılabilir. Ama velinin erişiminin habersiz kapanması karışıklık yaratabilir, o yüzden onay adımı önerilir.

## 5. Kapsam dışı olduğu konuşulanlar (bilgi için)
Ek talep olarak ayrıca değerlendirilir:
- Manyetik kart / turnike entegrasyonu
- Müdürlüğe sunulan liste ve raporların sistemden üretilmesi
- Kayıt formunun / izin belgesinin sistemde oluşturulması veya taranmış kopyasının saklanması
- Lisans / federasyon belgesi düzenleme
- Online kredi kartı ödemesi, e-fatura
- Performans takip modülü

## 6. Teknik borçlar ve fikirler
- Yük testi için gerçek sayıya yakın sentetik veri üreteci (Faz 5).
- Üretimde duman testi (E2E planı): [faz-plani.md](faz-plani.md) test stratejisi bölümü.
- Admin için yedek kurtarma kodları (2FA cihazı kaybolursa).
