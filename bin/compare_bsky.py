#!/usr/bin/env python3
"""A版（OpenClaw が実投稿）と B版（bsky_daily_b.py のシャドー出力）を並べて比較する。

使い方: python3 compare_bsky.py [YYYY-MM-DD ...]   （省略時は shadow/ にある全日付）
A版の本文は Bluesky の公開APIから、トークンは `openclaw cron runs` から取る。
機械検証は B版のコードと同じ基準（台風番号の実在・3行・内部ID・AI明記・300字）をA版にも適用する。
"""
import json
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SHADOW = Path(__file__).resolve().parent.parent / "shadow"
JST = timezone(timedelta(hours=9))
ACTOR = "uehr.bsky.social"
CRON_ID = "7c515a83-6054-432c-bd5b-fc35f3b4d960"


def a_posts(date):
    """その日のA版投稿（🤖で始まるもの）を新しい順に返す"""
    url = f"https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor={ACTOR}&limit=30&filter=posts_no_replies"
    feed = json.load(urllib.request.urlopen(url, timeout=20))["feed"]
    out = []
    for f in feed:
        r = f["post"]["record"]
        t = datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00")).astimezone(JST)
        if t.strftime("%Y-%m-%d") == date and r["text"].startswith("🤖"):
            out.append((t.strftime("%H:%M"), r["text"]))
    return out


def a_tokens():
    o = subprocess.run(["openclaw", "cron", "runs", "--id", CRON_ID], capture_output=True, text=True).stdout
    try:
        d = json.loads(o[o.find("{"):])
    except Exception:
        return {}
    res = {}
    for e in d.get("entries", d.get("runs", [])):
        day = datetime.fromtimestamp(e["runAtMs"] / 1000, JST).strftime("%Y-%m-%d")
        res.setdefault(day, []).append((e.get("usage") or {}).get("total_tokens"))
    return res


def check(text, real):
    pr = []
    for n in re.findall(r"台風(\d+)号", text):
        if n not in real:
            pr.append(f"存在しない台風{n}号")
    if re.search(r"台風\d{4}|TC\d{4}", text):
        pr.append("内部ID表記")
    if len([ln for ln in text.splitlines() if ln.strip()]) != 3:
        pr.append("3行でない")
    if "\n\n" in text:
        pr.append("空行あり")
    if not text.startswith("🤖AIによる自動生成"):
        pr.append("AI明記なし")
    if "台風情報なし" in text and real:
        pr.append("台風があるのに『台風情報なし』")
    elif real and "台風" not in text:
        pr.append("台風に言及なし（台風が存在）")
    return pr


def main():
    dates = sys.argv[1:] or sorted(p.name[:10] for p in SHADOW.glob("*_B.json"))
    toks = a_tokens()
    for date in dates:
        b = json.loads((SHADOW / f"{date}_B.json").read_text())
        real = set(b["real_typhoons"])
        print(f"\n===== {date} =====")
        for hhmm, text in a_posts(date):
            pr = check(text, real)
            print(f"[A OpenClaw {hhmm}] 問題: {pr or 'なし'} / トークン(当日の実行): {toks.get(date)}")
            print(text)
        print(f"\n[B コード+LLM] {b['mode']} / 問題: {b['problems'] or 'なし'} / トークン: {b['tokens']} / 取得{b['sec_facts']}s+LLM{b['sec_llm']}s")
        print(b["text"])


if __name__ == "__main__":
    main()
