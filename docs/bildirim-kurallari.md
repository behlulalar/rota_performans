# Bildirim kuralları ve kontroller

Velilere giden bildirimlerde uygulanan kurallar, alınan kararlar ve WhatsApp için planlanan ban koruması.
Durum: 5 Kasım 2026. Uygulama bildirimi (push) ve WhatsApp gönderimi (Evolution API, ban koruması) arka uçta hazır.

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
| Devamsızlık (`ders_gelmedi`) | Öğrenci "gelmedi" işaretlenince | **Geri alma penceresi:** varsayılan 3 dk bekler (Ayarlar'dan 1–15 dk). Bu sürede yoklama düzeltilirse bildirim iptal olur, hiç gitmez; sebep değiştirilirse aynı bildirim yeni sebeple yeniden bekletilir. Telafi derslerinde oluşmaz. Metin sebebi yazar: "… dersine katılmadı (Raporlu). Telafi hakkı tanımlanacaktır, ay sonuna kadar kullanılabilir." Habersiz (`devamsiz`): "… (Habersiz). Habersiz devamsızlıkta ders hakkı kullanılmış sayılır, telafi tanımlanmaz." Sebebi olmayan eski kayıtlar eski metinle gider. Antrenörün iç notu (açıklama) mesaja hiçbir zaman girmez |
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

## 4. WhatsApp: gönderim ve ban koruması (Faz 4.4, Evolution API)

Kulübe ait, kişisel kullanılmayan ayrı bir WhatsApp numarası kullanılır.

**Bağlantı:** Yönetici veya teknik destek Ayarlar > WhatsApp bağlantısı kartından QR okutarak numarayı bağlar, durumu görür ve bağlantıyı keser (denetim kaydına yazılır). Evolution API `docker-compose.yml` içinde `evolution` servisi olarak çalışır (sürüm sabit: v2.3.7, ayrı `evolution` veritabanı). Ayarlar: `EVOLUTION_URL`, `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE`. Durum uç noktası (`GET /api/whatsapp`) ayrıca devre kesici durumunu (`devre_kesici: {acik, sebep}`) ve kuyrukta bekleyen WhatsApp sayısını (`bekleyen_sayisi`) verir.

**Gönderim:** İşçi (`app/isci.py`) her 30 saniyede push'tan sonra `app/whatsapp_gonder.py` içindeki `whatsapp_gonder` işlevini çağırır. Mesaj, Evolution `POST /message/sendText/{instance}` ile (`delay` alanı "yazıyor…" göstergesi için) gider. Bağlantı `bagli` değilse ya da WhatsApp yapılandırılmamışsa **hiçbir satıra dokunulmaz**, satırlar bağlanınca gönderilir. Planlı zamanı 24 saatten eski bekleyen satır gönderilmez, `iptal` olur ("süresi geçti").

**Kime:**
- Yalnız WhatsApp izni (rıza) olan birincil iletişim kişileri; numara kişinin telefonundan alınır (`+90…` yazımındaki `+` gönderimde atılır).
- Aynı numaraya tek mesaj: duyurularda kardeşler tek alıcıdır (bkz. bölüm 1).
- Hiç konuşulmamış numaralara toplu ilk mesaj riski: velilerden kulüp numarasını kaydetmeleri istenecek (operasyonel).

**Hız ve zaman (hepsi sunucuda uygulanır):**
- **Döngü başına en fazla 1 mesaj.** İki gönderim arası **rastgele 25–70 sn**; her gönderimden sonra Redis'te yeni rastgele aralık seçilir. Mesajdan önce 1,5–4 sn "yazıyor…" göstergesi.
- **Saatlik üst sınır 50, günlük 250** (varsayılan; Ayarlar > WhatsApp'tan saatlik 1–200, günlük 1–1000). Sayım veritabanındaki gönderilmiş WhatsApp bildirimlerinden yapılır: saatlik = son 60 dakika, günlük = İstanbul takvim günü. Sonucu belirsiz kalan (gönderilmiş olabilecek) mesajlar da sayıma girer.
- **Isınma (yeni numara):** ilk gönderimin yapıldığı günden itibaren günlük sınır: **gün 1–3: 20**, **gün 4–7: 50**, **gün 8–14: 120**, 15. günden sonra ısınma sınırı yok. Geçerli günlük sınır her zaman `min(ayardaki sınır, ısınma sınırı)`dır. Isınma "ilk başarılı gönderim"den sayılır; numara değişirse takvim kendiliğinden sıfırlanmaz (gerekirse eski gönderim kayıtları temizlenmelidir).
- **Gönderim penceresi: 09:00–21:00 (İstanbul, 21:00 dahil değil)**, Ayarlar'dan değiştirilebilir (başlangıç 0–23, bitiş 1–24, başlangıç < bitiş). Pencere dışındaki satırlar bekler, pencere açılınca gider.

**İçerik:**
- Her kişisel şablonun aynı anlama gelen **3 söylenişi** vardır (`SOYLENISLER`, `app/bildirim.py`), hepsi "Rota Performans Akademi" imzalı ve öğrenci adıyla. Seçim bildirim kimliğine göredir (`id % 3`): rastgele değil, deterministik. Duyuru metni olduğu gibi gider.
- **Mesajda link yoktur.** Mesaja ve günlüğe/hata alanına telefon numarası ya da öğrenci adı yazılmaz (hata alanında yalnız genel sebep metni: "WhatsApp servisi hatası", "gönderim sonucu belirsiz" vb.).

**Öncelik:**
- Kişisel mesajlar (devamsızlık, ders hakkı) toplu duyurunun önüne geçer; kendi içinde planlı zamana göre sıralanır.

**Push varsa WhatsApp'ı atla (ayar: `wa_push_varsa_atla`, varsayılan açık):**
- Alıcının hesabı varsa ve son 30 günde başarılı push almış (`son_kullanim` dolu) bir cihazı varsa, aynı bildirimin WhatsApp satırı `iptal` olur, hata alanı "push ile ulaşıyor" yazar.
- Kural yalnız hesabı olan alıcıda işler; ayrıca aynı bildirimin push satırı gerçekten bu alıcı için bulunmalı ve hatalı/iptal olmamalıdır (veli push'u kapattıysa ya da push başarısızsa WhatsApp gider; yoksa mesaj hiç ulaşmazdı).
- **Duyuruda istisna:** duyuru oluşturulurken "her iki kanaldan gönder" (`her_iki_kanal`) seçilirse kural uygulanmaz. Duyuru yalnız WhatsApp kanalındaysa da uygulanmaz.

**Hata ve devre kesici:**
- Bağlantı kurulamayan (mesaj kesin gitmemiş) geçici hata: `2^deneme` dakika sonra yeniden denenir, en çok **5 deneme**, sonra "hatalı" olur.
- **Belirsiz sonuç** (istek gitti ama yanıt gelmedi: zaman aşımı, bağlantı kopması, sunucu 5xx): mesaj gitmiş olabilir, bu yüzden **yeniden denenmez**; satır "hatalı / gönderim sonucu belirsiz" olur, yönetici isterse elle yeniden deneyebilir.
- Numara WhatsApp'ta yoksa satır kalıcı "hatalı" olur (devre kesiciyi etkilemez).
- **Devre kesici:** art arda **3 gönderim hatası** ya da bağlantı kopması/servise ulaşılamaması Redis'te "açık" bayrağını kurar (**30 dk**, sebep metniyle) ve gönderim durur. Süre dolduğunda ve bağlantı `bagli` ise kendiliğinden kapanır; başarılı gönderim art arda hata sayacını sıfırlar. Yönetici ekranı `devre_kesici` alanından uyarıyı gösterir.
- **Hiçbir mesaj iki kez gitmez:** gönderimden önce satır "belirsiz" olarak veritabanına yazılır ve commit edilir; sonuç (başarı ya da kesin hata) sonra güncellenir. İşçi gönderim sırasında çökerse o mesaj yeniden gönderilmez. Her mesajdan sonra commit edilir.
- Uygulama bildirimi ve WhatsApp ayrı izlenir (Bildirimler ekranında kanal filtresi, her duyuruda kanal başına sonuç).

## 5. Duyurular ve ders iptali (yönetici)

- Hedef: bir ders oturumu, seçilen gruplar veya tüm aktif öğrenciler.
- Göndermeden önce özet gösterilir (kaç veli, kaçı uygulama bildirimi alacak, kaçında kapalı) ve onay istenir.
- **Ders iptali:** yoklaması alınmış ders iptal edilemez; o derse planlanmış telafiler kaldırılır, telafi hakkı yeniden planlanabilir olur. İptalden sonra "Velilere bildirilsin mi?" sorulur. Antrenör ders iptal edemez.
- WhatsApp seçeneği yalnız numara bağlıyken kabul edilir (bağlı değilse "WhatsApp bağlı değil"). "Her iki kanaldan gönder" seçilmezse push ile ulaşılan veliye WhatsApp gönderilmez (bölüm 4).

## 6. Kararlar ve açık noktalar

1. **KARAR: Uygulama bildirimi açıksa WhatsApp gönderilmesin mi?** Ayarlanabilir; varsayılan "yalnız push ile ulaşılamıyorsa WhatsApp" (Ayarlar > `wa_push_varsa_atla`, açık). Duyuruda "her iki kanaldan gönder" seçeneği bu kuralı o duyuru için kapatır (ders iptali gibi önemli duyurular). Push "okundu" garantisi vermediği için (bkz. bölüm 3) son 30 günde başarılı bildirim almış cihaz şartı aranır.
2. **KARAR: Limitler ve ısınma.** Saatlik 50, günlük 250 (ayarlanabilir); ısınma gün 1–3: 20, gün 4–7: 50, gün 8–14: 120 (bölüm 4). Numaranın yaşına göre canlıda gözlemleyerek ayarlanır; ban belirtisinde önce ayardaki limitler düşürülür.
3. Açık: çok eski bir numara için ısınma takvimi otomatik atlanmaz (ilk gönderim kaydından hesaplanır); yedek numara ile hızlı geçiş henüz yok.
