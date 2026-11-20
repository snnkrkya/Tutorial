"""Komut satırı.

  python -m radar scan     # her 2 saatte: yeni sinyallerde ACİL fırsat varsa anında WhatsApp
  python -m radar digest   # her sabah: günün tam sunumu
  python -m radar collect  # sadece kaynakları test et (Claude çağrısı yok)

Ortak bayraklar:
  --dry-run                       WhatsApp'a göndermez, ekrana yazar
  --fixtures tests/fixtures       İnternet yerine örnek veriyle çalışır
  --mock-llm                      Claude yerine örnek rapor kullanır (maliyetsiz test)

Not: Repo public ise GitHub Actions logları da public'tir. Bu yüzden
strateji içeriği yalnızca --dry-run'da ekrana basılır; aksi halde loga
sadece sayılar yazılır.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .presenter import alert_messages, digest_messages
from .sources import Signal, collect_all
from .state import State

ALERT_MIN_URGENCY = int(os.environ.get("ALERT_MIN_URGENCY", "8"))
ALERT_MIN_SCORE = int(os.environ.get("ALERT_MIN_SCORE", "7"))
MAX_ALERTS_PER_RUN = 2
MAX_SIGNALS = 160


def _load_fixture_signals(folder: Path) -> list[Signal]:
    data = json.loads((folder / "signals.json").read_text())
    return [Signal(**{k: v for k, v in d.items() if k != "key"}) for d in data]


def _mock_report():
    from .strategist import Report

    return Report.model_validate_json(Path("tests/fixtures/report.json").read_text())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="radar")
    ap.add_argument("mode", choices=["scan", "digest", "collect"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fixtures", type=Path)
    ap.add_argument("--mock-llm", action="store_true")
    args = ap.parse_args(argv)

    if args.fixtures:
        signals, status = _load_fixture_signals(args.fixtures), {"fixtures": "ok"}
    else:
        signals, status = collect_all()
    print("Kaynak durumu:", json.dumps(status, ensure_ascii=False))
    print(f"Toplam sinyal: {len(signals)}")

    if args.mode == "collect":
        for s in signals[:60]:
            print(" ", s.line())
        return 0

    state = State.load()
    if args.mode == "scan":
        pool = [s for s in signals if state.is_new(s.key)]
        print(f"Yeni sinyal: {len(pool)}")
        if not pool:
            state.save()
            return 0
    else:
        pool = signals
    pool = pool[:MAX_SIGNALS]

    if args.mock_llm:
        report = _mock_report()
    else:
        from .strategist import analyze

        report = analyze(pool, args.mode, state.recent_titles())

    provider = "console" if args.dry_run else None

    if args.mode == "scan":
        hot = [
            o for o in report.opportunities
            if o.urgency >= ALERT_MIN_URGENCY and o.score >= ALERT_MIN_SCORE and not state.was_alerted(o.topic_key)
        ][:MAX_ALERTS_PER_RUN]
        print(f"Acil fırsat: {len(hot)}")
        if hot:
            from .notify import send_all

            n = send_all(alert_messages(hot), provider)
            print(f"Gönderilen mesaj: {n}")
            for o in hot:
                state.mark_alerted(o.topic_key)
                state.log({"type": "alert", "title": o.title})
    else:
        from .notify import send_all

        n = send_all(digest_messages(report, len(pool)), provider)
        print(f"Fırsat: {len(report.opportunities)} · Gönderilen mesaj: {n}")
        for o in report.opportunities:
            state.mark_alerted(o.topic_key)
            state.log({"type": "digest", "title": o.title})

    state.mark_seen([s.key for s in pool])
    state.save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
