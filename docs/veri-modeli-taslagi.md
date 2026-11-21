# Veri Modeli (v0.2)

**Durum: kodlandı.** Tüm tablolar `backend/app/models/` altında modellendi ve `alembic/versions/fa8de04c0f64_is_verisi_tablolari.py` geçişiyle kuruldu. Kurallar veritabanı düzeyinde (CHECK, UNIQUE, kısmi indeks, tetikleyici) uygulanır ve `tests/test_sema.py` ile kanıtlanır. Müşteriden gelen bilgilere göre değişirse yeni bir geçişle güncellenir.

Taslaktan farklar:
- Birincil kişi, `ogrenci.birincil_iletisim_id` yerine `iletisim_kisisi.birincil` işaretiyle tutulur (döngüsel yabancı anahtar olmasın diye). Öğrenci başına en çok bir birincil kişi veritabanında garantidir, "en az bir" kuralı kayıt servisinde zorunlu tutulacak.
- `telafi_plani` tablosu eklendi (telafi için kendi grubu dışındaki derse eklenme).
- `bildirim` mesaj metni yerine `sablon` ve kişisel veri içermeyen `parametreler` saklar.
- `kullanici.ad_soyad` eklendi. `ogrenci.is_synthetic` adı `sentetik` oldu. `odeme.not` adı `aciklama` oldu.

## 1. Alınan kararlar
- Kayıt formu **sistemde yok**. Müşteri kağıt formu kendisi doldurur, yönetici bilgileri kayıt sırasında sisteme girer.
- T.C. kimlik / pasaport: **yalnızca numara**. Kimlik görseli, fotokopisi ve izin belgesi taraması saklanmaz.
- Manyetik kart numarası ve Müdürlük raporları **kapsam dışı**.
- Yoklama ilk aşamada yalnızca **geldi / gelmedi**. Mazeret ve raporlu sonra eklenir.
- **Gelmedi** işaretlenen ders, **telafi hakkı** olarak sayaca eklenir ve sonraki dönemde kullanılır. Telafi son kullanma süresi **sonra** belirlenecek.
- **Birincil iletişim kişisi** kayıtta seçilir. Öğrenciye ait tüm bildirimler yalnızca ona gider.
- **Panel hesabı yalnızca birincil iletişim kişisine** verilir. Anne mi baba mı girerse girsin farketmez, aynı hesabı kullanırlar. Diğer ebeveyn ve "diğer" kişiler için panel hesabı **yoktur**, yalnızca iletişim bilgisi tutulur.
- **Reşit öğrenci** kendi hesabıyla girer. Ebeveynin ve diğer kişilerin paneli görmesi gerekmez, iletişim bilgileri yine de kayıtlı kalır.
- **Gelmedi:** o ders telafi dersine dönüşür (normal −1, telafi +1). Hak, yoklamada "gelmedi" işaretlendikten **1 saat sonra** sayaca düşer. Bu sürede antrenör hatayı düzeltirse hak hiç doğmaz.
- **Dondurma yok.** Dondurma veya ders almama durumunda öğrenci **inaktif** olur ve sistemde inaktif olarak kayıtlı kalır, silinmez.
- **Paket sistemi:** Aylık 8 ders gibi paketler tanımlanır (ileride 3, 6, 12 aylık ve özel ders). Her paketin sabit bir fiyatı vardır, kayıtta istenirse özel fiyat girilebilir. Yönetici "ödeme alındı" işaretleyince ders hakkı öğrenciye **otomatik** yüklenir.
- **Çok aylık paketlerde** dersler ödeme işaretlenince **tek seferde** yüklenir (örn. 3 aylık, aylık 8 ders = 24 ders). İlk aşamada yalnızca **aylık 8 ders** paketiyle başlanır, diğer paketlerin var olup olmadığı belirsiz olduğu için sonra eklenir.
- **Üye numarası sisteme eklenmeyecek.**
- Telafi son kullanma süresi müşteriye sorulacak, şimdilik boş.
- Fotoğraf yüklenir (öğrenci listesinde tanımak için).

## 2. Tablolar

### Hesaplar ve roller
| Tablo | Önemli alanlar | Not |
|---|---|---|
| `kullanici` | id (UUID), rol (`admin`/`antrenor`/`veli`/`ogrenci`), giris (telefon veya e-posta), sifre_ozeti, totp_gizli (yalnızca admin), aktif, son_giris | Şifre argon2. Admin için 2FA zorunlu |
| `antrenor` | id, kullanici_id, ad_soyad, telefon, aktif, foto_anahtar | Pasif olunca foto silinmez |

### Öğrenci ve iletişim
| Tablo | Önemli alanlar | Not |
|---|---|---|
| `ogrenci` | id (UUID), ad, soyad, anne_adi, baba_adi, dogum_tarihi, cinsiyet (`kadin`/`erkek`), kimlik_tur (`tc`/`pasaport`), kimlik_no_sifreli, kimlik_no_ozet (tekillik), foto_anahtar, durum (`aktif`/`pasif`), kayit_tarihi, kullanici_id (reşit için), sentetik | Kimlik no şifreli. Yinelenen kayıt `kimlik_no_ozet` ile yakalanır. Yaş < 5 ise uyarı |
| `iletisim_kisisi` | id, ogrenci_id, rol (`anne`/`baba`/`diger`/`kendisi`), ad_soyad, telefon, kullanici_id (**yalnızca birincil kişide dolu**), birincil, whatsapp_izni, push_izni | Formdaki 3 telefon sütunu + "diğer" kişiler. Birden çok `diger` olabilir |

**Kurallar**
- Her öğrencinin **tam olarak bir** birincil iletişim kişisi olur (kayıt tamamlanmaz aksi halde).
- Panel hesabı (`kullanici_id`) **yalnızca birincil kişide** olur. Diğer kişilerin hesabı açılmaz.
- Aynı veli birden çok çocuğun birincil kişisiyse (kardeşler), **aynı `kullanici` kaydı** her çocuğun satırına bağlanır. Böylece tek girişle hepsini görür.
- En az bir `diger` veya acil durum kişisi zorunlu (formdaki "kesinlikle yazılacaktır" şartı).
- Reşit öğrenci için birincil kişi `kendisi` olur ve hesap `ogrenci.kullanici_id` üzerindedir.

**18 yaş geçişi**
- Doğum günü 18'e ulaşan öğrenci için yönetici paneline bir uyarı düşer. Geçiş otomatik ve sessiz yapılmaz.
- Yönetici onaylayınca: öğrenciye kendi hesabı açılır, birincil kişi `kendisi` olur, velinin bu öğrenciye erişimi **kapanır**, bildirimler öğrencinin kendi numarasına gider.
- Veli aynı hesapla daha küçük bir kardeşi görüyorsa, hesap kardeş için açık kalır.

**İnaktif (pasif) öğrenci**
- Kaydı, bilgileri ve geçmişi silinmez.
- Grup listelerinde ve yoklamada görünmez, bildirim almaz, yeni aidat/paket oluşmaz.
- Yeniden aktif edilirken yeni bir paket atanır. Kalan hakların ne olacağı açık soru (aşağıda).
- Panel hesabına girişin ne olacağı açık soru (aşağıda).

### Grup ve program
| Tablo | Önemli alanlar | Not |
|---|---|---|
| `grup` | id, ad, antrenor_id, kontenjan, aktif | |
| `grup_programi` | id, grup_id, gun, baslangic, bitis | Haftalık yineleyen slot (1 giriş = 90 dk) |
| `ogrenci_grup` | ogrenci_id, grup_id, baslangic, bitis | Bir öğrenci birden fazla slota bağlanabilir (örn. Çarşamba ve Cuma) |
| `ders_oturumu` | id, grup_id, grup_programi_id, tarih, baslangic, bitis, antrenor_id (yerine bakan), durum | Programdan üretilen somut ders |
| `telafi_plani` | id, oturum_id, ogrenci_id, olusturan_id | Öğrencinin kendi grubu dışındaki bir derse telafi için eklenmesi. Yoklamada `telafi_mi` ile eşleşir |

### Yoklama ve ders hakkı (defter)
| Tablo | Önemli alanlar | Not |
|---|---|---|
| `yoklama` | id, oturum_id, ogrenci_id, durum (`geldi`/`gelmedi`), isaretleyen_id, zaman, hareket_planli_zaman, hareket_islendi | Tek kayıt: öğrenci başına oturum başına bir yoklama. `gelmedi` için planlı zaman = işaret zamanı + 1 saat |
| `ders_hakki_hareketi` | id, ogrenci_id, sayac (`normal`/`telafi`), miktar (+/−), tur, donem, yoklama_id, neden, olusturan_id, zaman, son_kullanma (boş) | **Silinmez, değiştirilmez**. Bakiye = hareketlerin toplamı |

**Hareket türleri**
- `paket_yuklemesi`: ödeme işaretlenince normal +N (pakete göre)
- `ders_kullanimi`: geldi → normal −1
- `devamsizlik`: gelmedi → normal −1 ve telafi +1 (yoklamadan 1 saat sonra, tek işlemde)
- `telafi_kullanimi`: telafi −1
- `manuel_duzeltme`: yönetici, neden zorunlu
- `iptal`: ters kayıt (ödeme geri alınırsa veya 1 saatten sonra yoklama düzeltilirse)

**1 saat kuralı:** Arka plan işi, planlı zamanı gelen `gelmedi` yoklamalarını işler. İşlerken yoklama hâlâ `gelmedi` mi diye tekrar bakar. Değişmişse hareket yazmaz. 1 saatten sonra yapılan düzeltme `iptal` hareketiyle geri alınır (silme yok). WhatsApp/push bildirimi bu süreden **bağımsız**, kısa geri alma penceresi kuralı geçerli kalır.

`son_kullanma` (Kasım 2026, geçiş `fcbb49787e58`): devamsızlık telafisinde dersin ayının son günü (İstanbul takvimi). Yoklamada `gelmedi` için sebep zorunludur (`izinli`, `raporlu`, `yarisma`: telafi doğar; `devamsiz`: yalnızca normal −1, telafi doğmaz) ve isteğe bağlı iç not `aciklama` (veliye gösterilmez). Kullanılmayan telafi hakkı ay sonunda `telafi_suresi_doldu` hareketiyle düşer; telafi hakları en eskiden tüketilir. Süre dolumu bir uzlaştırmadır: günlük işçi işi ve her yoklama düzeltmesi, olması gereken yanma ile yazılmış olan arasındaki farkı (gerekirse artı yönde, yine yeni satırla) yazar. Geçiş anında var olan haklar geriye dönük yanmaz: son günleri en erken geçişin yapıldığı ayın sonudur. Yöneticinin elle verdiği telafi hakkı süresizdir (`son_kullanma` boş).

Her hareket tek veritabanı işleminde yazılır. Aynı yoklama iki kez hareket üretemez (tekil kısıt).

### Paket, aidat ve ödeme
| Tablo | Önemli alanlar | Not |
|---|---|---|
| `paket` | id, ad, tur (`aylik`/`3_aylik`/`6_aylik`/`yillik`/`ozel_ders`), ders_sayisi, sure_ay, varsayilan_fiyat, aktif | Yönetici tanımlar. İlk pakette aylık 8 ders |
| `ogrenci_paketi` | id, ogrenci_id, paket_id, ders_sayisi, liste_fiyati, uygulanan_fiyat, fiyat_ozel_mi, fiyat_degistiren_id, baslangic, bitis, durum (`odeme_bekliyor`/`odendi`/`iptal`) | Paket atandığında oluşur. Aidat satırı budur |
| `odeme` | id, ogrenci_paketi_id, tutar, tarih, yontem, not, olusturan_id | "Ödeme alındı" işaretlenince yazılır |

**Akış**
1. Öğrenciye paket seçilir. **Ücret** kutusunda paketin fiyatı görünür. Tıklanınca **"Farklı fiyat gir"** seçeneği açılır, girilen tutar `uygulanan_fiyat` olur ve `fiyat_ozel_mi` işaretlenir. Liste fiyatı da saklanır, böylece indirim izlenebilir.
2. Durum `odeme_bekliyor` olur. Ders hakkı **henüz yüklenmez**.
3. Yönetici **"ödeme alındı"** işaretler. Tek veritabanı işleminde: `odeme` kaydı yazılır, durum `odendi` olur, `paket_yuklemesi` hareketi eklenir.
4. Aynı pakete iki kez yükleme yapılamaz (tekil kısıt). Ödeme geri alınırsa `iptal` hareketi yazılır, denetim kaydı tutulur.

### Bildirim
| Tablo | Önemli alanlar | Not |
|---|---|---|
| `bildirim` | id, ogrenci_id, alici_iletisim_id, kanal (`whatsapp`/`push`), sablon, parametreler, yoklama_id, durum, planli_zaman, gonderim_zamani, deneme, hata | `planli_zaman` geri alma penceresini taşır |
| `push_abonelik` | id, kullanici_id, endpoint, anahtarlar, cihaz | Çıkışta silinir |

Alıcı her zaman öğrencinin birincil iletişim kişisidir. Birincil kişinin hesabı yoksa yalnızca WhatsApp gider.

### Güvenlik ve uyum
| Tablo | Önemli alanlar | Not |
|---|---|---|
| `denetim_kaydi` | id, kullanici_id, islem, hedef_tur, hedef_id, zaman, ip | Admin işlemleri, T.C. no görüntüleme, silme, ders hakkı düzeltmesi. Kişisel veri içermez |
| `riza` | id, ogrenci_id, tur (`aydinlatma`/`foto`/`whatsapp`), verildi_tarih, geri_cekildi_tarih | Rızanın alındığını kaydeder |
| `antrenor_foto_rizasi` | id, antrenor_id, verildi, geri_cekildi (boş = aktif rıza), kaydeden_id, geri_ceken_id | Antrenör foto rızası. Aktif rıza en fazla bir. Yükleme aktif rıza ister; geri çekilince foto silinir |

## 3. Erişim kuralları
| Veri | Admin | Antrenör | Panel hesabı sahibi (birincil veli veya reşit öğrenci) |
|---|---|---|---|
| T.C. kimlik no (tam) | Evet, kayıtlı | Hayır | Hayır |
| Doğum tarihi | Evet | Hayır | Kendi öğrencisi |
| Fotoğraf | Evet | Kendi grubunun öğrencileri | Yalnızca kendi öğrencisi |
| Acil durum kişisi | Evet | Kendi grubunun öğrencileri | Kendi öğrencisi |
| Yoklama | Evet | Kendi grupları | Kendi öğrencisi |
| Ders hakkı, aidat | Evet | Hayır | Kendi öğrencisi |
| Antrenör fotoğrafı | Evet | Evet (tümü) | Evet |

Antrenör fotoğrafını giriş yapmış herkes görür (destek/teknik destek dahil). Öğrenci ve antrenör fotoğrafı, öğrenci/antrenör pasif olunca **silinmez**. Fotoğraf yalnızca yönetici tarafından ya da (antrenörde) rıza geri çekilince silinir.

## 4. Açık sorular
Kapananlar: gelmedi normal dersi telafiye çevirir (evet), panel hesabı yalnızca birincil kişide (evet), reşit öğrencide veli erişimi yok (evet).

Kapananlar: telafi hakkı yoklamadan 1 saat sonra doğar, dondurma yok (inaktif), ders hakkı ödeme işaretlenince yüklenir.

1. **Çok aylık paketlerde hak geçerlilik süresi** paket süresi kadar mı? (Yükleme tek seferde, karar verildi. Bu soru yalnızca bu paketler gerçekten varsa gündeme gelir.)
2. **Özel ders:** Program ve yoklama nasıl işleyecek? (Tek öğrencilik grup, kendi antrenörü, ders sayısı pakete göre değişken.)
3. **Kısmi ödeme veya taksit** var mı, yoksa ödeme hep tek seferde mi?
4. **Paket süresi ne zaman başlar:** Ödeme tarihinde mi, ay başında mı? (Formda kart hakları 1 ay geçerli yazıyor.)
5. **İnaktif öğrencinin** kalan ders hakkı ve telafi hakkı ne olur? Yeniden aktif olunca geri gelir mi, yoksa silinir mi?
6. **İnaktif öğrencinin panel hesabı** kapanır mı, geçmişi görmeye devam eder mi?
7. **Telafi son kullanma süresi** (müşteriye sorulacak, şimdilik boş).

Birincil kişi değişikliğinde hesap devri: [dusunulecekler.md](dusunulecekler.md).
