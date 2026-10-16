#!/opt/homebrew/bin/python3
"""Slack DM への通知（OpenClaw の Slack 接続を `openclaw message send` 経由で使う）。

宛先は ~/.config/bsky/slack_to（1行、例: slack:Uxxxxxxxx）。環境変数 BSKY_NOTIFY_TO があればそれを優先。
通知の失敗で本体の処理を止めない（例外は握りつぶして False を返す）。
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

TO_FILE = Path.home() / ".config" / "bsky" / "slack_to"


def _target():
    t = os.environ.get("BSKY_NOTIFY_TO", "").strip()
    if not t and TO_FILE.exists():
        t = TO_FILE.read_text().strip()
    return t


def send(text):
    """Slack DM へ送る。成功したら True"""
    to = _target()
    exe = shutil.which("openclaw") or "/opt/homebrew/bin/openclaw"
    if not to:
        print("通知先が未設定のため通知しない", file=sys.stderr)
        return False
    try:
        r = subprocess.run([exe, "message", "send", "--channel", "slack", "--target", to, "-m", text[:3500]],
                           capture_output=True, text=True, timeout=90)
        if r.returncode != 0:
            print("Slack通知に失敗:", (r.stderr or r.stdout).strip()[:200], file=sys.stderr)
        return r.returncode == 0
    except Exception as e:  # 通知の失敗で本体を止めない
        print("Slack通知で例外:", e, file=sys.stderr)
        return False


if __name__ == "__main__":
    ok = send(" ".join(sys.argv[1:]) or "【Bluesky自動投稿】通知のテスト")
    sys.exit(0 if ok else 1)
