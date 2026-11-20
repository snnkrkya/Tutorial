"""Raporu WhatsApp'ta okunacak 'sunum' mesajlarına çevirir.

WhatsApp biçimlendirmesi: *kalın*, _italik_, ```kod```. Her fırsat ayrı
bir 'slayt' (mesaj) olur; uzun mesajlar sağlayıcı sınırına göre bölünür.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .strategist import Opportunity, Report

TZ = ZoneInfo("Europe/Istanbul")


def _bar(n: int) -> str:
    n = max(0, min(10, n))
    return "▰" * n + "▱" * (10 - n)


def opportunity_slide(o: Opportunity, header: str) -> str:
    acts = "\n".join(f"{i+1}. {a}" for i, a in enumerate(o.first_actions[:3]))
    src = "\n".join(o.sources[:3])
    return f"""{header}*{o.title}*
_{o.business_line}_

Skor  {_bar(o.score)} {o.score}/10
Aciliyet  {_bar(o.urgency)} {o.urgency}/10

*Sinyal:* {o.trend_signal}
*Neden şimdi:* {o.why_now}

*Para modeli:* {o.money_model}
*Tahmin:* {o.revenue_estimate}
*İlk gelir:* {o.time_to_first_revenue}

*Bugün yap:*
{acts}

*Otomatik:* {o.automatable}
*Onayın gerekir:* {o.needs_approval}

*Risk:* {o.main_risk}
*Hamle:* {o.mitigation}
*Bırakma kriteri:* {o.kill_criteria}
{src}""".strip()


def digest_messages(report: Report, signal_count: int) -> list[str]:
    now = datetime.now(TZ)
    opps = report.opportunities
    index = "\n".join(f"{i+1}. {o.title} · {o.score}/10" for i, o in enumerate(opps)) or "Bugün eşiği geçen fırsat yok."
    noise = "\n".join(f"· {n}" for n in report.ignored_noise[:5])
    cover = f"""*SCK GELİR RADARI*
{now:%d.%m.%Y · %H:%M}

*Net hüküm:* {report.verdict}

*Gündem*
{index}

_{signal_count} sinyal tarandı._"""
    if noise:
        cover += f"\n\n*Elenen gürültü*\n{noise}"
    msgs = [cover]
    msgs += [opportunity_slide(o, f"*{i + 1}/{len(opps)}* · ") for i, o in enumerate(opps)]
    msgs.append("_Onaylamak istediğin fırsatı söyle; uygulama planını, metinleri ve otomasyonu hazırlayayım._")
    return msgs


def alert_messages(opps: list[Opportunity]) -> list[str]:
    return [opportunity_slide(o, "*⚡ SICAK FIRSAT*\n\n") for o in opps]


def split_message(text: str, limit: int) -> list[str]:
    """Paragraf sınırından bölerek limiti aşmayan parçalar üretir."""
    if len(text) <= limit:
        return [text]
    parts, cur = [], ""
    for para in text.split("\n"):
        while len(para) > limit:  # tek satır bile çok uzunsa kes
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(para[:limit])
            para = para[limit:]
        if len(cur) + len(para) + 1 > limit:
            parts.append(cur)
            cur = para
        else:
            cur = f"{cur}\n{para}" if cur else para
    if cur:
        parts.append(cur)
    return parts
