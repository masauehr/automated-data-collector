# Bluesky 自動投稿

毎朝の気象要約を Bluesky に投稿する。天気図・衛星画像の解説ページ（weather_chart_vlm）へのリンクカード付き。

## 構成

| 要素 | 場所 | 備考 |
|---|---|---|
| 投稿スクリプト | `bin/bsky_post.py`（本リポジトリが正本） | 実行コピーは `~/.openclaw/workspace/bin/bsky_post.py`。標準ライブラリのみ |
| 認証 | `~/.openclaw/bsky.env`（権限600・リポジトリ外） | 雛形は `bin/bsky.env.example`。アプリパスワードを使用 |
| cron | `bsky-weather-am`（id `7c515a83-6054-432c-bd5b-fc35f3b4d960`） | 毎日 09:25 JST、haiku／fallback sonnet、結果は Slack DM にも返る |
| リンク先 | https://masauehr.github.io/weather_chart_vlm/webui/index.html | 毎朝 8:45 JST に Mac から更新 |

## 投稿の仕様

- 3行構成・250字以内（Bluesky 上限300字。超過時はスクリプトが末尾を切る）
  1. 「🤖AIによる自動生成」で始め、日付と全国の天気概況（気圧配置）
  2. 地域ごとの特徴と今日→明日の変化
  3. 警報・台風・地震などの注意点（なければ「特に警戒すべき情報なし」）
- 本文に URL・ハッシュタグは入れない（URL はリンクカードで付く）
- カード説明文は「AIが天気図・衛星画像を自動収集して解説する試み（自動生成・誤りを含む場合あり）」
- 通常の投稿であり、返信（reply）ではない（2026-10-10 に API で確認）

## 運用コマンド

```bash
openclaw cron list --all                                          # 無効ジョブも表示
openclaw cron run 7c515a83-6054-432c-bd5b-fc35f3b4d960 --wait --expect-final   # 手動実行（実投稿される）
openclaw cron enable|disable 7c515a83-6054-432c-bd5b-fc35f3b4d960
python3 bin/bsky_post.py --dry-run --text "テスト"                 # 投稿せず内容確認
```

※ cron は短縮ID（先頭8桁）だと `cron run` が失敗する。フルIDを使う。

## 変更履歴

- 2026-10-09: スクリプトと cron を作成（認証待ちで無効）
- 2026-10-10: 3行・AI自動生成明記に変更、リンク先ページにも注記追加、試験投稿2回の後に有効化
