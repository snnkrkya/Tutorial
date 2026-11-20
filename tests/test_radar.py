import json
from pathlib import Path

from radar.__main__ import main
from radar.presenter import digest_messages, split_message
from radar.sources import parse_google_trends, parse_wikipedia_top
from radar.state import State
from radar.strategist import Report

FIX = Path(__file__).parent / "fixtures"

GT_XML = """<?xml version="1.0"?><rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0"><channel>
<item><title>gta 6</title><ht:approx_traffic>500K+</ht:approx_traffic>
<ht:news_item><ht:news_item_title>Fragman yayında</ht:news_item_title><ht:news_item_url>https://x.y/z</ht:news_item_url></ht:news_item></item>
</channel></rss>"""


def test_parse_google_trends():
    s = parse_google_trends(GT_XML, "TR")
    assert s[0].title == "gta 6" and "500K+" in s[0].metric and s[0].url == "https://x.y/z"


def test_parse_wikipedia_skips_main_page():
    data = {"items": [{"articles": [{"article": "Ana_Sayfa", "views": 9}, {"article": "Grand_Theft_Auto_VI", "views": 5}]}]}
    s = parse_wikipedia_top(data, "tr.wikipedia")
    assert [x.title for x in s] == ["Grand Theft Auto VI"]


def test_split_message_respects_limit():
    text = "\n".join(["satır " * 30] * 20)
    parts = split_message(text, 500)
    assert all(len(p) <= 500 for p in parts)
    assert "".join(parts).replace("\n", "") == text.replace("\n", "")


def test_digest_render():
    r = Report.model_validate_json((FIX / "report.json").read_text())
    msgs = digest_messages(r, 6)
    assert "SCK GELİR RADARI" in msgs[0] and len(msgs) == 4


def test_scan_end_to_end_dedupes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("RADAR_STATE", str(tmp_path / "s.json"))
    assert main(["scan", "--dry-run", "--fixtures", str(FIX), "--mock-llm"]) == 0
    out = capsys.readouterr().out
    assert "SICAK FIRSAT" in out and "Acil fırsat: 1" in out
    # ikinci çalıştırma: aynı sinyaller artık yeni değil -> mesaj yok
    assert main(["scan", "--dry-run", "--fixtures", str(FIX), "--mock-llm"]) == 0
    assert "Yeni sinyal: 0" in capsys.readouterr().out
