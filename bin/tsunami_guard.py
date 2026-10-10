#!/usr/bin/env python3
"""津波情報の「状態判定」と「固定文」と「投稿前の検査」。標準ライブラリのみ。

目的: 毎朝の定期投稿で、津波に関する記述を間違えない（過大表現・見落とし・古い情報・取得失敗の誤認を防ぐ）。
  - LLM に津波の文面を書かせない。状態に応じた固定文（気象庁の表現そのまま）をコードが決める
  - 投稿の直前に、本文の津波の記述が固定文と一致するか検査する（bsky_post.py から呼ぶ）
津波の緊急通知は別系統で受け取る前提のため、ここでは「定期投稿が間違えないこと」だけを扱う。

使い方:
  python3 tsunami_guard.py status                 # {"level","sentence",...} を JSON 出力
  python3 tsunami_guard.py check --text "本文"    # 合格 exit 0 / 不合格 exit 1
"""
import argparse
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

URL = "https://www.jma.go.jp/bosai/tsunami/data/list.json"
JST = timezone(timedelta(hours=9))
LINK = "気象庁の最新情報を確認してください。"

# 重い順。「不明」は未知の種別（過小評価を避けるため、予報より重く扱う）
RANK = {"大津波警報": 5, "津波警報": 4, "津波注意報": 3, "不明": 2, "津波予報": 1, "なし": 0}
# 発表からこの時間を過ぎた情報は無視する（予報は短く、警報級は長く見る）
WINDOW = {"津波予報": timedelta(hours=24), "不明": timedelta(hours=72),
          "津波注意報": timedelta(hours=72), "津波警報": timedelta(hours=72), "大津波警報": timedelta(hours=72)}
ALERTS = ("大津波警報", "津波警報", "津波注意報", "津波予報")  # 前方一致の優先順


def fetch(timeout=20):
    with urllib.request.urlopen(URL, timeout=timeout) as r:
        return json.load(r)


def _kind_level(kind):
    """種別文字列 → レベル。解除系は None（無視）、未知は「不明」"""
    if not kind:
        return None
    if "解除" in kind or "なし" in kind and "津波" in kind:
        return None
    for name in ALERTS:
        if kind.startswith(name):
            return name
    return "不明"


def classify(items, now=None):
    """津波情報リスト（list.json）→ 状態。純粋関数（テスト用に now を注入できる）"""
    now = now or datetime.now(JST)
    if items is None:
        return {"level": "取得失敗", "sentence": f"津波情報を取得できませんでした。{LINK}", "detail": "fetch failed"}
    # 地震(eid)ごとに最新の1件だけを見る（警報→注意報→解除 の切り替えを正しく追う）
    latest = {}
    for it in items:
        key = it.get("eid") or id(it)
        cur = latest.get(key)
        if cur is None or (it.get("rdt", ""), it.get("ser", 0)) >= (cur.get("rdt", ""), cur.get("ser", 0)):
            latest[key] = it
    best, best_item = "なし", None
    for it in latest.values():
        if it.get("ift") in ("取消", "解除") or "解除" in (it.get("ttl") or ""):
            continue
        levels = [_kind_level(k.get("kind", "")) for k in it.get("kind", [])]
        levels = [lv for lv in levels if lv]
        if not levels:
            # 種別が空: 見出しだけで判断せず「不明」にする（見落としより安全側）
            ttl = it.get("ttl") or ""
            levels = ["不明"] if ttl and "予報" not in ttl and "解除" not in ttl else []
        if not levels:
            continue
        lv = max(levels, key=lambda x: RANK[x])
        try:
            rdt = datetime.fromisoformat(it["rdt"])
        except Exception:
            continue
        if now - rdt > WINDOW[lv]:
            continue
        if RANK[lv] > RANK[best]:
            best, best_item = lv, it
    return {"level": best, "sentence": _sentence(best, best_item), "detail": (best_item or {}).get("eid", "")}


def _sentence(level, item):
    """状態 → 固定文（気象庁の表現そのまま。独自の安全宣言・被害の見通しは書かない）"""
    if level == "なし":
        return ""
    if level == "津波予報":
        src = (item or {}).get("anm") or "地震"
        return f"{src}の地震で津波予報（若干の海面変動）が発表されています。{LINK}"
    if level in ("大津波警報", "津波警報", "津波注意報"):
        return f"{level}が発表されています。{LINK}"
    return f"津波に関する情報が発表されています。{LINK}"  # 不明


def current_state():
    try:
        items = fetch()
    except Exception:
        items = None
    return classify(items)


def check_text(text, state):
    """本文の津波の記述を検査。問題のリスト（空なら合格）"""
    problems = []
    sentence = state["sentence"]
    if state["level"] == "なし":
        if "津波" in text:
            problems.append("津波情報は発表されていないのに本文が津波に言及している")
        return problems
    if sentence not in text:
        problems.append(f"津波の固定文が本文にない（状態: {state['level']}）")
        return problems
    rest = text.replace(sentence, "")
    if "津波" in rest:
        problems.append("固定文以外にも津波の記述がある（過大・過小表現のおそれ）")
    return problems


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    c = sub.add_parser("check")
    c.add_argument("--text", required=True)
    a = ap.parse_args()
    st = current_state()
    if a.cmd == "status":
        print(json.dumps(st, ensure_ascii=False, indent=2))
        return 0
    probs = check_text(a.text, st)
    for p in probs:
        print("津波ガード不合格:", p)
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
