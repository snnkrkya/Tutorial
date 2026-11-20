"""Trend sinyal toplayıcıları.

Her toplayıcı hata verirse sessizce boş liste döner; tek bir kaynağın
çökmesi tüm radarı durdurmaz. Tümü anahtarsız çalışır, YouTube hariç
(YOUTUBE_API_KEY varsa devreye girer).
"""

from __future__ import annotations

import hashlib
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

import requests

UA = "sck-trend-radar/1.0 (+personal research bot)"
TIMEOUT = 20


@dataclass
class Signal:
    source: str
    title: str
    detail: str = ""
    url: str = ""
    metric: str = ""

    @property
    def key(self) -> str:
        norm = re.sub(r"\W+", " ", self.title.lower()).strip()
        return hashlib.sha1(f"{self.source}|{norm}".encode()).hexdigest()[:16]

    def line(self) -> str:
        parts = [f"[{self.source}] {self.title}"]
        if self.metric:
            parts.append(f"({self.metric})")
        if self.detail:
            parts.append(f"— {self.detail[:180]}")
        if self.url:
            parts.append(f"<{self.url}>")
        return " ".join(parts)

    def to_dict(self) -> dict:
        return asdict(self) | {"key": self.key}


def _get(url: str, **kw) -> requests.Response:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT, **kw)
    r.raise_for_status()
    return r


# --------------------------------------------------------------------------
# Google Trends günlük trend aramalar (RSS)
# --------------------------------------------------------------------------
HT = "{https://trends.google.com/trending/rss}"


def parse_google_trends(xml_text: str, geo: str) -> list[Signal]:
    root = ET.fromstring(xml_text)
    out: list[Signal] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        traffic = (item.findtext(f"{HT}approx_traffic") or "").strip()
        news = item.find(f"{HT}news_item")
        detail, url = "", ""
        if news is not None:
            detail = (news.findtext(f"{HT}news_item_title") or "").strip()
            url = (news.findtext(f"{HT}news_item_url") or "").strip()
        if title:
            out.append(Signal(f"GoogleTrends-{geo}", title, detail, url, f"{traffic} arama"))
    return out


def google_trends(geo: str) -> list[Signal]:
    r = _get(f"https://trends.google.com/trending/rss?geo={geo}")
    return parse_google_trends(r.text, geo)


# --------------------------------------------------------------------------
# Wikipedia en çok okunanlar (dün) — "GTA 6 çıktı" tipi olayları erken yakalar
# --------------------------------------------------------------------------
_WIKI_SKIP = re.compile(r"^(Ana_Sayfa|Main_Page|Özel:|Special:|Vikipedi:|Wikipedia:|Dosya:|File:|-$)")


def parse_wikipedia_top(data: dict, project: str, limit: int = 25) -> list[Signal]:
    articles = data.get("items", [{}])[0].get("articles", [])
    out = []
    for a in articles:
        name = a.get("article", "")
        if _WIKI_SKIP.match(name):
            continue
        out.append(
            Signal(
                f"Wikipedia-{project.split('.')[0]}",
                name.replace("_", " "),
                url=f"https://{project}.org/wiki/{name}",
                metric=f"{a.get('views', 0):,} görüntülenme/gün",
            )
        )
        if len(out) >= limit:
            break
    return out


def wikipedia_top(project: str) -> list[Signal]:
    d = datetime.now(timezone.utc) - timedelta(days=1)
    url = (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
        f"{project}/all-access/{d:%Y/%m/%d}"
    )
    return parse_wikipedia_top(_get(url).json(), project)


# --------------------------------------------------------------------------
# Google News başlıkları (RSS)
# --------------------------------------------------------------------------
def parse_rss(xml_text: str, source: str, limit: int = 20) -> list[Signal]:
    root = ET.fromstring(xml_text)
    out = []
    for item in list(root.iter("item"))[:limit]:
        title = (item.findtext("title") or "").strip()
        if title:
            out.append(Signal(source, title, url=(item.findtext("link") or "").strip()))
    return out


def google_news(query: str | None, hl: str = "tr", gl: str = "TR") -> list[Signal]:
    base = "https://news.google.com/rss"
    params = {"hl": hl, "gl": gl, "ceid": f"{gl}:{hl}"}
    if query:
        base += "/search"
        params["q"] = f"{query} when:1d"
    r = _get(base, params=params)
    label = f"GoogleNews-{gl}" + (f":{query}" if query else "")
    return parse_rss(r.text, label, limit=12 if query else 20)


# --------------------------------------------------------------------------
# Hacker News ön sayfa (teknoloji / AI / indie gelir trendleri)
# --------------------------------------------------------------------------
def hackernews() -> list[Signal]:
    data = _get("https://hn.algolia.com/api/v1/search", params={"tags": "front_page"}).json()
    return [
        Signal("HackerNews", h["title"], url=h.get("url") or "", metric=f"{h.get('points', 0)} puan")
        for h in data.get("hits", [])
        if h.get("title")
    ]


# --------------------------------------------------------------------------
# Reddit r/popular (Actions IP'lerinden zaman zaman 403 dönebilir)
# --------------------------------------------------------------------------
def reddit_popular() -> list[Signal]:
    data = _get("https://www.reddit.com/r/popular/hot.json", params={"limit": 30}).json()
    out = []
    for c in data.get("data", {}).get("children", []):
        p = c.get("data", {})
        out.append(
            Signal(
                f"Reddit-r/{p.get('subreddit', '?')}",
                p.get("title", ""),
                url="https://reddit.com" + p.get("permalink", ""),
                metric=f"{p.get('ups', 0):,} upvote",
            )
        )
    return out


# --------------------------------------------------------------------------
# YouTube trend videolar (opsiyonel, YOUTUBE_API_KEY gerekir)
# --------------------------------------------------------------------------
def youtube_trending(region: str) -> list[Signal]:
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        return []
    data = _get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "snippet,statistics", "chart": "mostPopular", "regionCode": region, "maxResults": 25, "key": key},
    ).json()
    out = []
    for v in data.get("items", []):
        sn, st = v.get("snippet", {}), v.get("statistics", {})
        out.append(
            Signal(
                f"YouTube-{region}",
                sn.get("title", ""),
                detail=sn.get("channelTitle", ""),
                url=f"https://youtu.be/{v.get('id')}",
                metric=f"{int(st.get('viewCount', 0)):,} izlenme",
            )
        )
    return out


# --------------------------------------------------------------------------
# Kaynak kayıt defteri — yeni kaynak eklemek için buraya bir satır ekle
# --------------------------------------------------------------------------
NEWS_QUERIES_TR = ["para kazanma", "viral trend", "yayıncı rekor", "yeni uygulama"]

COLLECTORS: list[tuple[str, Callable[[], list[Signal]]]] = [
    ("google_trends_TR", lambda: google_trends("TR")),
    ("google_trends_US", lambda: google_trends("US")),
    ("wikipedia_tr", lambda: wikipedia_top("tr.wikipedia")),
    ("wikipedia_en", lambda: wikipedia_top("en.wikipedia")),
    ("google_news_TR", lambda: google_news(None)),
    *[(f"google_news_{q}", (lambda q=q: google_news(q))) for q in NEWS_QUERIES_TR],
    ("hackernews", hackernews),
    ("reddit", reddit_popular),
    ("youtube_TR", lambda: youtube_trending("TR")),
]


def collect_all() -> tuple[list[Signal], dict[str, str]]:
    """Tüm kaynakları çalıştırır. (sinyaller, kaynak_durumu) döner."""
    signals: list[Signal] = []
    status: dict[str, str] = {}
    seen: set[str] = set()
    for name, fn in COLLECTORS:
        try:
            got = fn()
            status[name] = f"ok:{len(got)}"
        except Exception as e:  # noqa: BLE001 — kaynak hatası radarı durdurmamalı
            status[name] = f"hata:{type(e).__name__}"
            continue
        for s in got:
            if s.title and s.key not in seen:
                seen.add(s.key)
                signals.append(s)
    return signals, status
