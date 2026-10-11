# Bluesky 自動投稿

> **2026-10-11 に本番を B版（launchd＋コード＋LLM）に切り替えた。** A版（OpenClaw cron `bsky-weather-am`）は同日朝にモデル応答の停止で4回連続失敗したため無効化（削除はせず残置）。以下の A版（OpenClaw）の記述は旧本番の仕様・経緯。B版の仕様は末尾の「B版（現行）」を参照。

毎朝の気象要約を Bluesky に投稿する。天気図・衛星画像の解説ページ（weather_chart_vlm）へのリンクカード付き。

## 構成

| 要素 | 場所 | 備考 |
|---|---|---|
| 投稿スクリプト | `bin/bsky_post.py`（本リポジトリが正本） | 実行コピーは `~/.openclaw/workspace/bin/bsky_post.py`。標準ライブラリのみ |
| 認証 | `~/.openclaw/bsky.env`（権限600・リポジトリ外） | 雛形は `bin/bsky.env.example`。アプリパスワードを使用 |
| cron | `bsky-weather-am`（id `7c515a83-6054-432c-bd5b-fc35f3b4d960`） | 毎日 09:40 JST、haiku／fallback sonnet、結果は Slack DM にも返る |
| リンク先 | https://masauehr.github.io/weather_chart_vlm/webui/index.html | 毎朝 8:45 JST に Mac から更新 |

## 天気図VLM解説の参照とフォールバック（2026-10-10 追加）

気圧配置・気圧の谷・雨域の根拠として、天気図VLM解説（`~/projects/weather_chart_vlm/webui/history/<今日>/data.json`）を参照する。
理由: 独自取得だけだと奄美の雨（実際は気圧の谷による）の原因を取り違えるため。VLM は天気図を読んで原因まで書ける。

`bin/vlm_status.py` が機械的に判定し JSON を返す（LLM に判定させない）:
- **fail**（VLM なしで独自に書く）: 当日ファイルなし／日付が今日(JST)でない／確信度 0.5 未満／ガードレールに NG／JSON 読込失敗
- **ok**（VLM を参照）: 上記以外。ガードレール「注意」の項目（前線・台風・気圧の谷など）は `cautions` に入り、その話題は VLM を根拠にせず気象庁MCPで裏取りする
- 台風・警報・津波・地震は VLM に頼らず、常に気象庁MCP（`get_typhoon` 等）を正とする
- 最終回答に使ったモード（VLMあり／VLMなし＋理由）を返し、Slack DM で後から確認できる

実行コピー: `~/.openclaw/workspace/bin/vlm_status.py`（本リポジトリの `bin/` が正本）。
注意: VLM の更新は 8:45 開始だが遅れる日がある（10/10 は 9:35 完了）。9:40 に間に合わなければ自動的に fail → 独自取得になる。

## 元データの取り方（案B: 独立取得）

Slack のまとめ（weather-jp-am）は参照せず、Bluesky ジョブが気象庁MCPから自分で取得する。
必須ツール: `get_typhoon` / `get_warning` / `get_early_warning` / `get_tsunami_info` / `get_earthquake_info` / `get_forecast` / `get_forecaster_comment` / `get_daily_ranking`。
優先順位: 津波 > 台風 > 特別警報・警報 > 大雨・高波・強風 > 地震。取得に失敗した分野は「なし」と書かず触れない。
※ 2026-10-10 に Slack のまとめ（台風27・28・29号）と比較し、旧指示（`get_typhoon` 等が未指定）では「台風情報なし」と誤記していたため修正。
Slack のまとめを元にする案A（Slack と必ず一致するが Slack ジョブ失敗時は投稿なし）も検討したが、独立性を優先して案Bを採用。

### 台風の扱い（厳守）
表記は「台風29号（コグマ）」の形式。内部ID（2629 等）は本文に出さない（試験投稿で「台風2629・2628」と出たため修正）。
台風は `get_typhoon` の結果に載っているものだけを書く。Web検索・過去記事から台風を足さない（消滅・温帯低気圧化した台風を書かない）。
背景: 2026-10-10 の Slack まとめが、10/8 に温帯低気圧化済みの台風27号を現存するかのように書いた（実際は28・29号のみ）。

### VLM の台風記述は使わない（2026-10-10 追加）
VLM が「台風28号が本州南岸に近づく」と書き、気象庁の予報（日本の東で温帯低気圧化）と食い違ったため。
`vlm_status.py` が today/tomorrow から台風に触れる文（台風・台28号・熱帯低気圧など）を**丸ごと除外**して出力する（`typhoon_sentences_removed: true`）。台風は `get_typhoon` の結果だけを正とする。A版は指示文にも明記。テスト: `tests/test_vlm_status.py`。

## 津波ガード（2026-10-10 追加）

津波の誤り（過大表現・見落とし・古い情報・取得失敗の誤認）は致命的なため、LLM に津波の文面を書かせない。
津波の緊急通知は別系統で受け取る前提で、毎朝の定期投稿が「間違えないこと」だけを担保する。

- `bin/tsunami_guard.py`: 気象庁の津波情報から状態を判定（大津波警報／津波警報／津波注意報／津波予報／不明／なし／取得失敗）→ 状態ごとの**固定文**（気象庁の表現そのまま。独自の安全宣言・被害の見通しは書かない）
  - 地震(eid)ごとに最新の1件だけを見る（警報→注意報→解除の切り替えを追う）。解除は無視。古い情報は無視（予報24時間・警報級72時間）。未知の種別は「不明」＝見落とさない。取得失敗は「なし」にしない
- **投稿直前の検査**: `bin/bsky_post.py` が本文を検査し、津波がなしなのに「津波」を含む／固定文が無い／固定文以外にも津波の記述がある、のいずれかなら**投稿しない**（ガードを実行できない場合も投稿しない）。A版・B版の両方を守る
- A版（OpenClaw）: 指示文で `tsunami_guard.py status` を exec し、sentence を一字一句3行目の先頭に入れる。`get_tsunami_info` は使わせない
- B版: プロンプトから津波の事実を外し、コードが固定文を3行目の先頭に挿入
- Slack まとめ（weather-jp-am）: 同じ規則を指示文に追加（Slack 側には投稿前の検査がないため、人の目が最後の砦）
- テスト: `python3 -m unittest discover -s tests`（13件）。種別の文字列は実データでは「津波予報（若干の海面変動）」のみ確認済み。注意報以上・解除の書式は気象庁の仕様に基づく想定で、未観測

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
- 2026-10-10: 天気図VLM解説の参照（失敗時は独自取得）を追加。`bin/vlm_status.py` 新設
- 2026-10-10: 投稿時刻を 9:25 → 9:40 に変更（VLM 更新が遅れる日があるため）。VLM参照モードで試験投稿し、気圧の谷による雨を正しく反映することを確認。1段落になった問題に対し改行ルールを追加
- 2026-10-10: 津波ガードを追加（固定文＋投稿前検査）。Slack まとめにも同規則を追加
- 2026-10-10: VLM 出力から台風に触れる文を除外（台風は get_typhoon のみ）

## B版（現行・2026-10-11〜）

| 要素 | 内容 |
|---|---|
| 実行 | launchd `com.user.bsky_daily_b`、毎日 **9:40 JST**、`bsky_daily_b.py --post`（設定の正本: 本リポジトリの `com.user.bsky_daily_b.plist`） |
| 事実の取得 | コードが `jma_mcp/server.py` の関数を直接呼ぶ（台風・地震・警報47府県・観測値）。津波は `tsunami_guard.py` の固定文 |
| 文章化 | `claude --print --model claude-haiku-4-5`（サブスク経由）1回。機械検証に落ちたら指摘付きで1回だけ再生成 |
| 投稿 | 検証・津波ガードに合格したときだけ `bsky_post.py` で投稿。不合格なら投稿しない（`shadow/<日付>_B.json` に `post_skipped`） |
| 記録 | `shadow/YYYY-MM-DD_B.json`（本文・モード・トークン・問題・投稿結果）、ログ `shadow/launchd.log` |
| 通知 | **なし**（失敗しても静かに終わる。要改善: Slack へ結果通知） |

運用: `launchctl list | grep bsky_daily_b` ／ 手動実行 `/opt/homebrew/bin/python3 bin/bsky_daily_b.py [--post]` ／ 停止 `launchctl bootout gui/501/com.user.bsky_daily_b`
A版に戻す場合: `openclaw cron enable 7c515a83-6054-432c-bd5b-fc35f3b4d960` と B版の停止（二重投稿を避ける）。
- 2026-10-11: 本番を B版に切り替え（A版は無効化）。今日分は B版の手動実行で投稿
