#!/usr/bin/env python3
"""A版（OpenClaw 非公開の内部実行）と B版（launchd 本番）を並べて比較する。

使い方: python3 compare_bsky.py [YYYY-MM-DD ...]   （省略時は shadow/ にある全日付）
どちらも shadow/YYYY-MM-DD_{A,B}.json から読む。A版のトークンは `openclaw cron runs` から取る。
機械検証は同じ基準を両方に適用する（台風番号の実在・3行・空行・内部ID・AI明記・「台風情報なし」の矛盾・
津波ガード・VLM由来の台風記述の混入など）。意味の言い過ぎは人が見る。
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SHADOW = HERE.parent / "shadow"
JST = timezone(timedelta(hours=9))
A_CRON_ID = "348e8844-f81c-4898-9e6e-867720cd1347"  # bsky-internal-a（非公開の内部実行）


def a_tokens():
    o = subprocess.run(["openclaw", "cron", "runs", "--id", A_CRON_ID], capture_output=True, text=True).stdout
    try:
        d = json.loads(o[o.find("{"):])
    except Exception:
        return {}
    res = {}
    for e in d.get("entries", d.get("runs", [])):
        day = datetime.fromtimestamp(e["runAtMs"] / 1000, JST).strftime("%Y-%m-%d")
        res.setdefault(day, []).append(((e.get("usage") or {}).get("total_tokens"), e.get("status")))
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
        pr.append("先頭が『🤖AIによる自動生成』でない")
    if len(text) > 300:
        pr.append(f"300字超過({len(text)})")
    if "台風情報なし" in text and real:
        pr.append("台風があるのに『台風情報なし』")
    elif real and "台風" not in text:
        pr.append("台風に言及なし（台風が存在）")
    return pr


def load(date, label):
    f = SHADOW / f"{date}_{label}.json"
    return json.loads(f.read_text()) if f.exists() else None


def main():
    dates = sys.argv[1:] or sorted({p.name[:10] for p in SHADOW.glob("*_[AB].json")})
    toks = a_tokens()
    summary = {"A": 0, "B": 0}
    for date in dates:
        a, b = load(date, "A"), load(date, "B")
        real = set((b or {}).get("real_typhoons", []))  # 台風の正解は B版が取得した get_typhoon の結果
        print(f"\n===== {date} =====  （実在する台風: {sorted(real) or '不明'}）")
        for label, rec in (("A OpenClaw・非公開", a), ("B launchd・本番", b)):
            if rec is None:
                print(f"[{label}] 記録なし（実行されなかった／失敗）")
                continue
            pr = check(rec["text"], real) if real else ["（正解の台風が不明のため台風検査は省略）"]
            pr += [f"津波ガード: {p}" for p in rec.get("tsunami_guard_problems", [])]
            pr += rec.get("problems", []) if label.startswith("B") else []
            extra = f"トークン {rec['tokens']}" if "tokens" in rec else f"トークン(当日の実行) {toks.get(date)}"
            print(f"[{label}] 機械検査: {sorted(set(pr)) or 'OK'} / {extra} / {rec.get('mode', '')}")
            print(rec["text"])
            summary[label[0]] += len(set(pr))
    print(f"\n機械検査の指摘数の合計  A: {summary['A']}  B: {summary['B']}  （意味の言い過ぎ・地名・数値は人が確認）")


if __name__ == "__main__":
    main()
