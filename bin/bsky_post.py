#!/usr/bin/env python3
"""Bluesky へ気象情報＋解説ページへのリンクカードを投稿する（標準ライブラリのみ）。

使い方:
  python3 bsky_post.py --text "本文" [--url URL] [--card-title T] [--card-desc D] [--dry-run]
  本文は --text の代わりに標準入力からも渡せる。

認証情報は ~/.config/bsky/bsky.env（権限600）から読む。内容は表示しない。
  BSKY_HANDLE=xxxx.bsky.social
  BSKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx   # アプリパスワード（メインのパスワードは使わない）
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

PDS = "https://bsky.social"
ENV_PATH = Path.home() / ".config" / "bsky" / "bsky.env"
MAX_LEN = 300  # Bluesky の本文上限（grapheme）
DEFAULT_URL = "https://masauehr.github.io/weather_chart_vlm/webui/index.html"


def load_env(path):
    """KEY=VALUE 形式の env を読む（値は戻り値のみ。表示しない）"""
    if not path.exists():
        sys.exit(f"認証ファイルがありません: {path}")
    if path.stat().st_mode & 0o077:
        sys.exit(f"権限が緩すぎます。chmod 600 {path} を実行してください")
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("\"'")
    return env


def api(method, nsid, body, token=None):
    """XRPC 呼び出し（JSON）"""
    req = urllib.request.Request(
        f"{PDS}/xrpc/{nsid}",
        data=json.dumps(body).encode(),
        method=method,
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def link_facets(text):
    """本文中のURLをリンク化する facet を作る（位置は UTF-8 バイト単位）"""
    facets = []
    for m in re.finditer(r"https?://[^\s]+", text):
        start = len(text[: m.start()].encode())
        end = start + len(m.group().encode())
        facets.append({
            "index": {"byteStart": start, "byteEnd": end},
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": m.group()}],
        })
    return facets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", help="本文（省略時は標準入力）")
    ap.add_argument("--url", default=DEFAULT_URL, help="リンクカードのURL")
    ap.add_argument("--card-title", default="天気図・衛星画像のAI解説（気象庁データ）")
    ap.add_argument("--card-desc", default="AIが天気図・衛星画像を自動収集して解説する試み（自動生成・誤りを含む場合あり）")
    ap.add_argument("--dry-run", action="store_true", help="投稿せず内容だけ表示")
    ap.add_argument("--shadow", metavar="ラベル", help="投稿せず shadow/<日付>_<ラベル>.json に本文と津波ガード結果を保存する（A/B比較用の非公開実行）")
    a = ap.parse_args()

    text = (a.text if a.text is not None else sys.stdin.read()).strip()
    if not text:
        sys.exit("本文が空です")
    if len(text) > MAX_LEN:
        # 超過時は末尾を「…」で切る（LLM要約が長すぎた場合の保険）
        text = text[: MAX_LEN - 1] + "…"

    # 津波ガード: 本文の津波の記述が現在の状態（固定文）と一致しなければ投稿しない。
    # ガードが読み込めない場合も投稿しない（安全側に倒す）
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import tsunami_guard
        problems = tsunami_guard.check_text(text, tsunami_guard.current_state())
    except Exception as e:
        sys.exit(f"津波ガードを実行できないため投稿しません: {type(e).__name__}")
    if a.shadow:
        import datetime as _dt
        d = Path.home() / "openclaw_prj" / "projects" / "automated-data-collector" / "shadow"
        d.mkdir(exist_ok=True)
        day = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=9))).strftime("%Y-%m-%d")
        rec = {"date": day, "label": a.shadow, "text": text, "tsunami_guard_problems": problems, "posted": False}
        (d / f"{day}_{a.shadow}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2))
        print(f"[shadow:{a.shadow}] 保存のみ（投稿しない） {len(text)}文字 津波ガード: {'不合格 ' + ' / '.join(problems) if problems else '合格'}")
        return
    if problems:
        sys.exit("津波ガード不合格のため投稿しません: " + " / ".join(problems))

    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "langs": ["ja"],
        "createdAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "embed": {
            "$type": "app.bsky.embed.external",
            "external": {"uri": a.url, "title": a.card_title, "description": a.card_desc},
        },
    }
    facets = link_facets(text)
    if facets:
        record["facets"] = facets

    if a.dry_run:
        print(f"[dry-run] {len(text)}文字")
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return

    env = load_env(ENV_PATH)
    sess = api("POST", "com.atproto.server.createSession",
               {"identifier": env["BSKY_HANDLE"], "password": env["BSKY_APP_PASSWORD"]})
    res = api("POST", "com.atproto.repo.createRecord",
              {"repo": sess["did"], "collection": "app.bsky.feed.post", "record": record},
              token=sess["accessJwt"])
    print("投稿完了:", res["uri"])


if __name__ == "__main__":
    main()
