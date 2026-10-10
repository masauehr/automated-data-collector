# Bluesky 自動投稿

毎朝の気象要約を Bluesky に投稿する。天気図・衛星画像の解説ページ（weather_chart_vlm）へのリンクカード付き。

## 構成

| 要素 | 場所 | 備考 |
|---|---|---|
| 投稿スクリプト | `bin/bsky_post.py`（本リポジトリが正本） | 実行コピーは `~/.openclaw/workspace/bin/bsky_post.py`。標準ライブラリのみ |
| 認証 | `~/.openclaw/bsky.env`（権限600・リポジトリ外） | 雛形は `bin/bsky.env.example`。アプリパスワードを使用 |
| cron | `bsky-weather-am`（id `7c515a83-6054-432c-bd5b-fc35f3b4d960`） | 毎日 09:25 JST、haiku／fallback sonnet、結果は Slack DM にも返る |
| リンク先 | https://masauehr.github.io/weather_chart_vlm/webui/index.html | 毎朝 8:45 JST に Mac から更新 |

## 元データの取り方（案B: 独立取得）

Slack のまとめ（weather-jp-am）は参照せず、Bluesky ジョブが気象庁MCPから自分で取得する。
必須ツール: `get_typhoon` / `get_warning` / `get_early_warning` / `get_tsunami_info` / `get_earthquake_info` / `get_forecast` / `get_forecaster_comment` / `get_daily_ranking`。
優先順位: 津波 > 台風 > 特別警報・警報 > 大雨・高波・強風 > 地震。取得に失敗した分野は「なし」と書かず触れない。
※ 2026-10-10 に Slack のまとめ（台風27・28・29号）と比較し、旧指示（`get_typhoon` 等が未指定）では「台風情報なし」と誤記していたため修正。
Slack のまとめを元にする案A（Slack と必ず一致するが Slack ジョブ失敗時は投稿なし）も検討したが、独立性を優先して案Bを採用。

### 台風の扱い（厳守）
台風は `get_typhoon` の結果に載っているものだけを書く。Web検索・過去記事から台風を足さない（消滅・温帯低気圧化した台風を書かない）。
背景: 2026-10-10 の Slack まとめが、10/8 に温帯低気圧化済みの台風27号を現存するかのように書いた（実際は28・29号のみ）。

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
- 2026-10-10: 指示文に台風・津波・地震ツールと優先順位を追加（「台風情報なし」誤記の再発防止）。Slack との比較評価の結果
- 2026-10-10: 「台風は get_typhoon の結果のみ」の制約を追加
