# SCK Gelir Radarı

Bilgisayar başında olmasan da 7/24 çalışan trend → strateji → WhatsApp sistemi.

```
 Kaynaklar (her 2 saatte)          Strateji motoru (Claude)             WhatsApp
 ─────────────────────────         ─────────────────────────            ─────────────
 Google Trends TR/US     ┐         SCK profili + yeni sinyaller         ⚡ Sıcak fırsat
 Wikipedia en çok okunan ├──────▶  → fırsat, para modeli, gelir   ───▶  (aciliyet ≥ 8)
 Google News (TR)        │           tahmini, ilk 3 eylem, risk,
 Hacker News, Reddit     │           bırakma kriteri, onay kapısı       Her sabah 08:41
 YouTube (opsiyonel)     ┘                                              tam sunum
```

- **Anlık tarama (her 2 saat):** Sadece *yeni* sinyalleri değerlendirir. GTA 6 fragmanı, slime yayını patlaması gibi saatler içinde kapanacak bir pencere varsa hemen WhatsApp'a "⚡ SICAK FIRSAT" düşer. Acil bir şey yoksa sessiz kalır.
- **Günlük sunum (08:41 İstanbul):** Kapak (net hüküm + gündem), her fırsat için bir slayt, elenen gürültü.
- **Tekrar yok:** Aynı konu 7 gün içinde ikinci kez uyarı olarak gelmez.
- **Onay kapısı:** Sistem önerir ve hazırlar; para harcama, mesaj/e-posta gönderme, yayına alma ve sözleşme her zaman senin onayında (manuel v2.0, bölüm 06-07).

## Kurulum (yaklaşık 15 dakika)

### 1. Repo'yu private yap (önerilir)
Repo şu an **public**. Public repolarda Actions logları herkese açıktır. Kod içeriği loga yazmıyor ama yine de *Settings → General → Danger Zone → Change visibility → Private*.

### 2. WhatsApp sağlayıcısı seç

| Sağlayıcı | Kurulum | Maliyet | Not |
|---|---|---|---|
| **CallMeBot** (önerilen başlangıç) | 2 dk | Ücretsiz | Sadece kendine mesaj. callmebot.com'daki WhatsApp adımlarıyla botun numarasına izin mesajı gönder, gelen API anahtarını al. |
| Twilio | 15 dk | Mesaj başı ücret | Sandbox her 72 saatte yeniden katılım ister; kalıcı kullanım için onaylı gönderici gerekir. |
| Meta WhatsApp Cloud API | 30+ dk | Konuşma başı | İşletme hesabı gerekir. Son 24 saatte bota yazmadıysan serbest metin yerine onaylı şablon ister. |

### 3. GitHub Secrets ekle
*Settings → Secrets and variables → Actions → New repository secret*

| Secret | Zorunlu | Açıklama |
|---|---|---|
| `ANTHROPIC_API_KEY` | Evet | console.anthropic.com'dan |
| `SCK_PROFILE` | Evet | `profile/profile.example.md` içeriğini kendi güncel bilgilerinle doldurup yapıştır (hassas C katmanı bilgi koyma) |
| `CALLMEBOT_PHONE` | CallMeBot ise | `+905xxxxxxxxx` |
| `CALLMEBOT_APIKEY` | CallMeBot ise | CallMeBot'tan gelen anahtar |
| `TWILIO_SID`, `TWILIO_TOKEN`, `TWILIO_FROM`, `WHATSAPP_TO` | Twilio ise | |
| `META_WA_TOKEN`, `META_WA_PHONE_ID`, `WHATSAPP_TO` | Meta ise | |
| `YOUTUBE_API_KEY` | Hayır | YouTube TR trend videoları kaynağını açar |

Opsiyonel *Variables*: `NOTIFY_PROVIDER` (`callmebot` varsayılan / `twilio` / `meta`), `ALERT_MIN_URGENCY` (8), `ALERT_MIN_SCORE` (7).

### 4. Varsayılan dala al ve test et
GitHub zamanlanmış iş akışlarını yalnızca **varsayılan dalda** çalıştırır. Bu dalı `main`'e birleştir, ardından *Actions → SCK Trend Radar → Run workflow → mode: digest*. Birkaç dakika içinde WhatsApp'a ilk sunum gelir.

> Public repolarda 60 gün commit olmazsa GitHub zamanlanmış işleri durdurur; Actions sekmesinden tek tıkla yeniden açılır.

## Yerel çalıştırma

```bash
pip install -r requirements.txt
python -m radar collect                                          # kaynakları test et
python -m radar digest --dry-run --fixtures tests/fixtures --mock-llm   # maliyetsiz deneme
ANTHROPIC_API_KEY=... python -m radar digest --dry-run           # gerçek analiz, WhatsApp'a göndermez
python -m pytest -q
```

## Maliyet (tahmini)
Model: `claude-opus-5-5`. Tarama başına ~10-15K girdi token. Günde 12 tarama + 1 sunum ≈ aylık **10-25 USD** aralığı (sinyal hacmine bağlı). Ucuzlatmak için `RADAR_MODEL` değişkeniyle başka model seçilebilir.

## Mimari

| Dosya | Görev |
|---|---|
| `radar/sources.py` | Kaynak toplayıcılar. Yeni kaynak = `COLLECTORS` listesine bir satır. |
| `radar/strategist.py` | Profil + sinyaller → yapılandırılmış `Report` (Pydantic). Değerlendirme ilkeleri `SYSTEM` içinde. |
| `radar/presenter.py` | WhatsApp sunum biçimi (kapak + slaytlar). |
| `radar/notify.py` | CallMeBot / Twilio / Meta gönderimi, bölme ve yeniden deneme. |
| `radar/state.py` | Görülen sinyaller ve gönderilen uyarılar (Actions cache'te tutulur, commit edilmez). |
| `.github/workflows/radar.yml` | 7/24 zamanlayıcı. |

## Yol haritası (7 / 30 / 90)

- **7 gün:** Bu sistem canlı; eşikleri (aciliyet/skor) ilk hafta gelen sinyallere göre ayarla.
- **30 gün:** WhatsApp'tan "1'i onayla" cevabı → n8n webhook → seçilen fırsat için teklif taslağı, DM metinleri ve içerik planı otomatik üretilip Drive/Notion'a düşer (gönderim yine onaylı).
- **90 gün:** Onaylanan fırsatların sonucu (lead, satış, TL) geri beslenir; radar hangi trend tipinin gerçekten para getirdiğini öğrenip skorlamayı buna göre ağırlıklandırır.
