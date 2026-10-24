# Rota Performans Akademi

[![CI](https://github.com/behlulalar/rota_performans/actions/workflows/ci.yml/badge.svg)](https://github.com/behlulalar/rota_performans/actions/workflows/ci.yml)

Yüzme kulübü yönetim sistemi. Planlar ve kararlar: [docs/](docs/).

## Geliştirme ortamı

Gereken: Docker. Portlar yalnızca `127.0.0.1`'e açılır ve makinedeki diğer servislerle çakışmasın diye varsayılandan farklıdır.

```bash
cp .env.example .env
sed -i '' "s/^JWT_SECRET=.*/JWT_SECRET=$(openssl rand -hex 32)/" .env   # macOS
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

| Servis | Adres |
|---|---|
| Arayüz | http://localhost:5174 |
| API | http://localhost:8100/api/saglik (geliştirmede şema: `/api/docs`) |
| PostgreSQL | `127.0.0.1:5434` (kullanıcı `rota`, veritabanı `rota`) |
| Redis | `127.0.0.1:6380` |

### Yönetici hesabı oluşturma
```bash
docker compose exec backend python -m app.cli admin-olustur ornek@kulup.com
```
Şifre en az 12 karakter olmalı ve komut satırından sorulur, geçmişe yazılmaz.

### Test
```bash
docker compose exec backend pytest -q
```
Testler `rota_test` veritabanını ve Redis 1. dizinini kullanır, geliştirme verisine dokunmaz.

### E2E testleri (Playwright)
Tarayıcı testleri `e2e/` klasöründedir. Geliştirme verisine dokunmamak için ayrı veritabanı (`rota_e2e`), ayrı Redis dizini (2), ayrı backend (`127.0.0.1:8101`) ve ayrı Vite sunucusu (`127.0.0.1:5175`) kullanılır.
```bash
cd e2e && npm install && npx playwright install chromium && cd ..   # bir kez
bash e2e/yerel-calistir.sh            # ortamı kurar, testleri çalıştırır, konteynerleri kapatır
```
Betik her çalıştırmada `rota_e2e` veritabanını sıfırlar ve yöneticiyi `python -m app.cli e2e-tohum` ile oluşturur. Bu komut yalnızca `ENV=test` veya `ENV=e2e` iken çalışır, aksi halde hata verir. Rapor: `e2e/playwright-report/`. CI'da aynı testler `e2e` işinde çalışır.

### Yeni veritabanı geçişi
```bash
docker compose exec backend alembic revision --autogenerate -m "aciklama"
docker compose exec backend alembic upgrade head
```

## Çalışma şekli: dal ve otomatik birleştirme
- Her özellik `ozellik/<kisa-ad>` adlı bir dalda geliştirilir ve GitHub'a gönderilir.
- GitHub Actions testleri çalıştırır (backend testleri, geçişlerin geri alınabilirliği, frontend derlemesi).
- **Testler geçerse** dal önce **Preview** ortamına kaydedilir, sonra **Production** adımında `main`'e aktarılır. Geçmezse `main` değişmez. Durum GitHub'da sağ kenardaki *Deployments* bölümünde görünür.
- Aktarım yalnızca ileri sarma (fast-forward) ile yapılır. `main` ilerlemişse dalı güncelle:
  `git fetch origin && git rebase origin/main && git push --force-with-lease`

- Dallar `main`'e girdikten sonra **silinmez**, GitHub'da Branches sekmesinde geçmiş olarak kalır.
- Her faz bitince `v0.N.0` biçiminde bir **sürüm etiketi** atılır. Etiket gönderilince GitHub Actions o fazın notlarıyla bir **Release** oluşturur.

```bash
git switch -c ozellik/ogrenci-kayit
# ... çalış, commit at ...
git push -u origin ozellik/ogrenci-kayit
```

## Yapı
```
backend/    FastAPI, SQLAlchemy, Alembic
frontend/   Vite + React + TypeScript + Tailwind
infra/      Veritabanı başlangıç betikleri (sunucu yapılandırmaları buraya gelecek)
docs/       Planlar. Müşteri/sözleşme dosyaları (pdf, docx) depoya girmez.
```

## Kurallar
- Gerçek öğrenci/veli verisi geliştirmede kullanılmaz. Sahte veri kullanılır.
- `.env` ve sırlar depoya girmez.
- Yetki kontrolü her uç noktada sunucuda yapılır ([docs/guvenlik-plani.md](docs/guvenlik-plani.md)).
