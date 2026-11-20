"""WhatsApp gönderim sağlayıcıları.

NOTIFY_PROVIDER ile seçilir:
  callmebot  Kişisel kullanım, ücretsiz, en hızlı kurulum (CALLMEBOT_PHONE, CALLMEBOT_APIKEY)
  twilio     Twilio WhatsApp (TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM, WHATSAPP_TO)
  meta       WhatsApp Cloud API (META_WA_TOKEN, META_WA_PHONE_ID, WHATSAPP_TO)
  console    Sadece ekrana yazar (yerel test)
"""

from __future__ import annotations

import os
import time

import requests

from .presenter import split_message

LIMITS = {"callmebot": 1500, "twilio": 1500, "meta": 4000, "console": 100000}


def _env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise RuntimeError(f"{name} ortam değişkeni eksik")
    return v


def _callmebot(text: str) -> None:
    r = requests.get(
        "https://api.callmebot.com/whatsapp.php",
        params={"phone": _env("CALLMEBOT_PHONE"), "text": text, "apikey": _env("CALLMEBOT_APIKEY")},
        timeout=30,
    )
    r.raise_for_status()
    if "ERROR" in r.text.upper()[:500] and "QUEUED" not in r.text.upper():
        raise RuntimeError("CallMeBot gönderimi reddetti")


def _twilio(text: str) -> None:
    sid = _env("TWILIO_SID")
    r = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        auth=(sid, _env("TWILIO_TOKEN")),
        data={"From": f"whatsapp:{_env('TWILIO_FROM')}", "To": f"whatsapp:{_env('WHATSAPP_TO')}", "Body": text},
        timeout=30,
    )
    r.raise_for_status()


def _meta(text: str) -> None:
    r = requests.post(
        f"https://graph.facebook.com/v21.0/{_env('META_WA_PHONE_ID')}/messages",
        headers={"Authorization": f"Bearer {_env('META_WA_TOKEN')}"},
        json={
            "messaging_product": "whatsapp",
            "to": _env("WHATSAPP_TO").lstrip("+"),
            "type": "text",
            "text": {"body": text, "preview_url": False},
        },
        timeout=30,
    )
    r.raise_for_status()


def _console(text: str) -> None:
    print("\n" + "─" * 40 + "\n" + text)


PROVIDERS = {"callmebot": _callmebot, "twilio": _twilio, "meta": _meta, "console": _console}


def send_all(messages: list[str], provider: str | None = None) -> int:
    provider = (provider or os.environ.get("NOTIFY_PROVIDER", "console")).lower()
    fn = PROVIDERS.get(provider)
    if fn is None:
        raise RuntimeError(f"Bilinmeyen NOTIFY_PROVIDER: {provider}")
    sent = 0
    for msg in messages:
        for part in split_message(msg, LIMITS[provider]):
            for attempt in range(3):
                try:
                    fn(part)
                    sent += 1
                    break
                except Exception as e:  # noqa: BLE001
                    if attempt == 2:
                        # URL'de API anahtarı/telefon olabilir; public loglara sızmasın.
                        code = getattr(getattr(e, "response", None), "status_code", "?")
                        raise RuntimeError(f"{provider} gönderimi başarısız ({type(e).__name__}, HTTP {code})") from None
                    time.sleep(5 * (attempt + 1))
            if provider != "console":
                time.sleep(3)  # sırayı korumak ve hız sınırına takılmamak için
    return sent
