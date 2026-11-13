#!/opt/homebrew/bin/python3
"""Bluesky 自動投稿の監視（launchd から毎日 10:00 に実行）。

bsky_daily_b.py は完了・見送り・異常終了のときだけ Slack に通知する。
そのため「CLI が固まって終わらない」「launchd が起動しなかった」場合は何も通知されない
（2026-11-09 に claude CLI のハングで投稿が約90分遅れ、通知もなかった）。
この監視は、締切時刻になっても今日の結果ファイル（shadow/YYYY-MM-DD_B.json）が無い、または有っても未投稿（posted が False）なら Slack に知らせる。
結果ファイルは本体の最後（投稿・通知の後）に書かれるため、存在すれば本体は終了している。
通知のみ行い、プロセスの停止や再実行は自動で行わない。
"""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import notify  # noqa: E402

JST = timezone(timedelta(hours=9))
SHADOW = HERE.parent / "shadow"
SCRIPT = "bsky_daily_b.py"


def running_processes():
    """bsky_daily_b.py の実行中プロセスと、その子（claude CLI 等）を [(pid, 経過時間, コマンド)] で返す"""
    try:
        out = subprocess.run(["ps", "-axo", "pid=,ppid=,etime=,command="], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return []
    rows = []
    for ln in out.splitlines():
        parts = ln.split(None, 3)
        if len(parts) == 4:
            rows.append((int(parts[0]), int(parts[1]), parts[2], parts[3]))
    roots = {pid for pid, _, _, cmd in rows if SCRIPT in cmd and "bsky_watchdog" not in cmd}
    return [(pid, et, cmd[:120]) for pid, ppid, et, cmd in rows if pid in roots or ppid in roots]


def build_message(now, shadow_dir, procs):
    """今日の結果ファイルが無ければ通知文を返す。あれば None"""
    today = now.strftime("%Y-%m-%d")
    f = Path(shadow_dir) / f"{today}_B.json"
    if f.exists():
        # 結果ファイルはあっても投稿されていない日（検査で見送り・投稿失敗）は知らせる。
        # 本体の見送り通知（9:4x）が届かなかった場合の保険（2026-11-13 に見送りの通知が確認できなかった）
        try:
            rec = json.loads(f.read_text())
        except Exception:
            return None
        if rec.get("posted") is False:
            why = rec.get("post_skipped") or "投稿に失敗"
            probs = "\n".join(f"  - {p}" for p in (rec.get("problems") or [])[:5])
            cmd = "cd ~/openclaw_prj/projects/automated-data-collector && /opt/homebrew/bin/python3 bin/bsky_daily_b.py --post"
            return f"【Bluesky自動投稿】{today} ⚠️ {now:%H:%M}時点で今日はまだ投稿されていません（{why}）。\n{probs}\n手動実行: {cmd}"
        return None
    head = f"【Bluesky自動投稿】{today} ⚠️ {now:%H:%M}になっても今日の投稿処理が完了していません。"
    if procs:
        lines = "\n".join(f"  PID {pid}（経過 {et}）{cmd}" for pid, et, cmd in procs)
        body = f"処理は実行中のまま止まっている可能性があります（claude CLI のハング等）。\n{lines}\n停止する場合: kill <PID>（子の claude → 親の順）"
    else:
        body = "実行中のプロセスはありません。launchd が起動しなかった（スリープ・設定不備）可能性があります。"
    cmd = "cd ~/openclaw_prj/projects/automated-data-collector && /opt/homebrew/bin/python3 bin/bsky_daily_b.py --post"
    return f"{head}\n{body}\n手動実行: {cmd}"


def main():
    msg = build_message(datetime.now(JST), SHADOW, running_processes())
    if msg:
        print(msg)
        notify.send(msg)


if __name__ == "__main__":
    main()
