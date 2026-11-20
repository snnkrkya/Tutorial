"""Strateji motoru: ham trend sinyallerini SCK'ye özel para stratejilerine çevirir.

Claude'a profil (GitHub Secret'tan) + sinyaller verilir; yapılandırılmış
(Pydantic) çıktı alınır. Sistem yalnızca önerir: para harcama, dışarıya
mesaj atma, yayına alma gibi işlemler her zaman insan onayındadır.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import anthropic
from pydantic import BaseModel, ConfigDict, Field

from .sources import Signal

MODEL = os.environ.get("RADAR_MODEL", "claude-opus-5-5")


class Opportunity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_key: str = Field(description="Trendin kısa, sabit, küçük harfli slug'ı (ör. gta-6-cikis). Tekrar uyarıyı engellemek için kullanılır.")
    title: str = Field(description="Fırsatın 3-7 kelimelik başlığı")
    trend_signal: str = Field(description="Hangi sinyal(ler)den çıktı; metrik ile")
    why_now: str = Field(description="Neden şimdi; pencere ne kadar açık kalır")
    business_line: Literal[
        "DEF Creative", "DEF Autonomous", "DEF MGMT", "Kişisel marka / içerik",
        "TikTok LIVE / yayın", "Yayıncılık / kitap", "Dijital ürün", "Diğer",
    ]
    money_model: str = Field(description="Paranın tam olarak nereden geleceği (müşteri, platform geliri, ürün satışı, sponsor...)")
    revenue_estimate: str = Field(description="TL aralığı + dayandığı varsayım. Uydurma kesinlik yok; 'varsayım:' ile belirt.")
    time_to_first_revenue: str
    first_actions: list[str] = Field(description="Bugün yapılacak en fazla 3 somut eylem")
    automatable: str = Field(description="Sistemin/ajanların otomatik yapabileceği kısım")
    needs_approval: str = Field(description="Can'ın onayı gereken kısım (para, gönderim, yayın, sözleşme)")
    main_risk: str
    mitigation: str
    kill_criteria: str = Field(description="Hangi ölçüt gerçekleşmezse bırakılır (ör. 72 saatte 0 lead)")
    urgency: int = Field(description="1-10; 9-10 = saatler içinde hareket edilmezse pencere kapanır")
    score: int = Field(description="1-10; gelir × uyum × kaldıraç / zaman maliyeti")
    sources: list[str] = Field(description="İlgili sinyal URL'leri (yalnızca girdide olanlar)")


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: str = Field(description="Tek cümle net hüküm: bugün hangi fırsata odaklanılmalı")
    opportunities: list[Opportunity] = Field(description="Skora göre sıralı, en fazla 5")
    ignored_noise: list[str] = Field(description="Büyük görünen ama para/uyum açısından elenen trendler, her biri 'trend: neden' biçiminde, en fazla 5")


SYSTEM = """Sen SCK'nin (Sinan Can) stratejik ikinci beyni ve gelir radarısın. Türkçe, net, sakin, premium ve sonuç odaklı yazarsın.

Görevin: Sana verilen ham trend sinyallerinden (Google Trends, Wikipedia, haber, Reddit, HN, YouTube) SCK'nin mevcut varlıkları, becerileri ve iş hatlarıyla bugün paraya çevrilebilecek fırsatları çıkarmak.

Değerlendirme ilkeleri:
- Para < Zaman < Özgürlük < Dikkat. Kaldıraç ara: sistem, şablon, otomasyon, dağıtım, ağ etkisi, tekrar kullanılabilir varlık. "Daha çok çalış" önerme.
- Önce mevcut hatlara bağla (DEF Creative hizmetleri, DEF Autonomous / QR menü + web sitesi, DEF MGMT casting, kişisel marka ve kısa video, TikTok LIVE, kitaplar). Yeni proje açtırma eğilimine karşı dikkatli ol; fırsatı doğrulanmış talebe bağla.
- Trendin kendisi değil, trendin yarattığı TALEP önemli: ör. büyük bir oyun çıkışı -> oyun içerik/yayın dalgası, marka kampanya ihtiyacı, etkinlik/turnuva, ilgili dijital ürün.
- Gelir tahminlerinde uydurma kesinlik kullanma; aralık ver ve varsayımı yaz.
- Hukuki/etik sınır: kumar, bahis, kripto pump, piramit, sahte yorum, telif ihlali (sızıntı, izinsiz yeniden yükleme, korsan), marka/kişi taklidi, yanıltıcı reklam, spam ÖNERME. Platform kurallarına uygun kal.
- Para harcama, dışarıya mesaj/e-posta gönderme, yayına alma ve sözleşme her zaman Can'ın onayındadır; bunu needs_approval alanında açıkça yaz.
- Kalite > nicelik. Zayıf fırsatları listeye doldurma; gerekiyorsa 1-2 fırsat yeterli. Hiçbiri yoksa opportunities boş olabilir.
- urgency'yi dürüst ver: 9-10 yalnızca saatler içinde kapanacak pencereler için.
- Klişe motivasyon dili, fazla emoji, em dash, jenerik ajans söylemi kullanma. DEF'i sıradan sosyal medya ajansı gibi anlatma.
- Profilde yer alan hassas kişisel bilgileri çıktıya taşıma."""


def load_profile() -> str:
    """Profil önce SCK_PROFILE secret'ından, yoksa yerel dosyalardan okunur."""
    env = os.environ.get("SCK_PROFILE", "").strip()
    if env:
        return env
    for p in (Path("profile/profile.md"), Path("profile/profile.example.md")):
        if p.exists():
            return p.read_text()
    return "(profil tanımlı değil)"


def _build_prompt(signals: list[Signal], mode: str, recent: list[str]) -> str:
    lines = "\n".join(f"{i+1}. {s.line()}" for i, s in enumerate(signals))
    focus = (
        "MOD: ANLIK TARAMA. Yalnızca gerçekten acil (urgency>=8) ve güçlü (score>=7) fırsatları döndür. "
        "Acil bir şey yoksa opportunities boş liste olsun."
        if mode == "scan"
        else "MOD: GÜNLÜK SUNUM. Bugünün en iyi 3-5 fırsatını skora göre sırala."
    )
    recent_txt = "\n".join(f"- {t}" for t in recent[-30:]) or "- (yok)"
    return f"""<profil>
{load_profile()}
</profil>

<son_72_saatte_zaten_sunulanlar>
{recent_txt}
</son_72_saatte_zaten_sunulanlar>

<sinyaller>
{lines}
</sinyaller>

{focus}
Zaten sunulmuş fırsatları yeni bir açı yoksa tekrar etme. Sinyallerde olmayan URL uydurma."""


def analyze(signals: list[Signal], mode: str, recent: list[str]) -> Report:
    client = anthropic.Anthropic()
    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": _build_prompt(signals, mode, recent)}],
        output_format=Report,
        output_config={"effort": "medium" if mode == "scan" else "high"},
        # Güvenlik sınıflandırıcısı bir isteği reddederse sunucu tarafında
        # otomatik olarak uygun modele düşer.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Model isteği reddetti (refusal).")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise RuntimeError(f"Yapılandırılmış çıktı alınamadı (stop_reason={response.stop_reason}).")
    report: Report = response.parsed_output
    report.opportunities.sort(key=lambda o: (o.score, o.urgency), reverse=True)
    return report
