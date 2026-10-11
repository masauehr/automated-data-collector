#!/bin/bash
# 本リポジトリの bin/ のスクリプトを OpenClaw の実行場所 ~/.openclaw/workspace/bin/ に反映する
# （OpenClaw の cron は実行コピーを使う。正本はこのリポジトリ）。使い方: bash bin/deploy_workspace.sh
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
DST="$HOME/.openclaw/workspace/bin"
mkdir -p "$DST"
for f in bsky_post.py tsunami_guard.py vlm_status.py; do
  if ! cmp -s "$SRC/$f" "$DST/$f"; then cp -p "$SRC/$f" "$DST/$f"; echo "更新: $f"; else echo "一致: $f"; fi
done
