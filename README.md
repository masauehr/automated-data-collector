# Automated Data Collector

cron の指示文・設定は [cron/](cron/README.md)（`bin/cron_sync.py` で git と同期）。詳しくは [bluesky-auto-post.md](bluesky-auto-post.md)（運用マニュアル）・[BLUESKY.md](BLUESKY.md)（Bluesky 投稿の仕様）・[COMPARE-A-B.md](COMPARE-A-B.md)（A/B比較）・[WORKLOG.md](WORKLOG.md)（作業記録）を参照。

気象・経済・AI の情報を自動で収集・要約し、Slack と Bluesky に配信する自動処理の運用リポジトリ。
（2026-10-10 時点の実態に更新。`openclaw cron list --all` が正）

**実行基盤は OpenClaw に限らない。** 始まりは OpenClaw の cron（Slack 配信、Bluesky A版）だったが、Bluesky 自動投稿は 2026-10-11 から **OpenClaw を使わない B版（launchd＋コード＋Claude Code CLI）が本番**になった。OpenClaw 上の cron（Slack のまとめ、Bluesky A版の内部比較）も継続している。

### 重要な教訓: Claude Code と MCP ツールの活用
- **開発・検証の中心は Claude Code**。気象庁MCPのツール（`get_typhoon` 等）を Claude Code から呼べたことで、OpenClaw 版の誤り（消滅済みの台風27号、「台風情報なし」、津波の言い過ぎ）を**権威あるデータと突き合わせて発見**できた。スクリプト・テスト・検証ルールも Claude Code で作った。
- **B版の設計**: 事実の取得は MCP サーバー（jma_mcp）の関数をコードで直接呼び、LLM（`claude --print`、サブスク経由）は文章化だけを担当。取得→検証→投稿をコードで固定し、機械検証に落ちたら投稿しない。
- **OpenClaw は MCP を登録して初めて同等に使える**。当初は MCP が1つも設定されておらず、指示文が「存在しないツール」を指していたことが A版失敗の主因だった（[COMPARE-A-B.md](COMPARE-A-B.md) の【訂正】）。2026-10-11 に `openclaw mcp add jma` で登録済み。
- 使い分けの目安: 毎回同じ手順で確実に回したいもの・誤りが許されないもの（防災情報の投稿）は「コード＋Claude Code CLI＋MCP」、調べものや会話を伴う軽い配信（Slack のまとめ）は OpenClaw。

## 関連リポジトリとの関係

OpenClaw まわりは複数のリポジトリに分かれている。**本リポジトリは「自動処理（cron・投稿）の運用」を担当**する（OpenClaw 上で動くものと、OpenClaw を使わず launchd＋Claude Code CLI で動くものの両方）。

| リポジトリ（場所） | 役割 | 本リポジトリとの関係 |
|---|---|---|
| **automated-data-collector**（本リポジトリ）`~/openclaw_prj/projects/automated-data-collector` | 運用中の自動処理: cron の指示文・設定（`cron/`）、Bluesky 自動投稿（B版本番・A版比較）、津波ガード等のスクリプト、作業記録 | — |
| **openclaw_common**（親）`~/openclaw_prj` / `masauehr/openclaw_common` | OpenClaw 運用の統合管理: 共通ドキュメント `common/`、AIエージェントの作業規則 `SECURITY-POLICY.md`、`CHANGELOG.md` | 本リポジトリは親の `projects/` 配下に置かれるが、**独立した git リポジトリ**。親は `.gitignore` で除外し、二重管理しない（2026-10-11 整理）。親の `SECURITY-POLICY.md` は `openclaw_prj/` 以下のみ編集可と定めている |
| **openclaw_setup** `~/projects/openclaw_setup` / `masauehr/openclaw_setup` | OpenClaw を Mac に**導入するまで**の作業記録（インストール、Slack 接続、設定、トラブル対処）と運用マニュアル `MANUAL.md` | 導入・基盤の話は setup、**導入後に動かす自動処理の変更は本リポジトリに記録**する（2026-10-11 方針）。`MANUAL.md` は `pc_docs` のコピー |
| **pc_docs** `~/projects/pc_docs` | 手順書の集約（`manuals/automation/`）。`openclaw.md`・`bluesky-auto-post.md`・`sns-auto-post-options.md` | 本リポジトリの `BLUESKY.md` 等の写し。更新時は両方を直す |
| **weather_chart_vlm** `~/projects/weather_chart_vlm` | 天気図・衛星のVLM解説（毎朝 8:45 更新、GitHub Pages） | Bluesky 投稿の**リンク先**であり、気圧配置の根拠として `history/<日付>/data.json` を読む（`bin/vlm_status.py`） |
| **jma_mcp** `~/projects/jma_mcp` | 気象庁MCPサーバー | B版が関数を直接 import、OpenClaw にも MCP `jma` として登録（`openclaw/mcp-jma.json`） |

OpenClaw 本体の設定・実行コピーは git 外の `~/.openclaw/`（`openclaw.json`、`workspace/bin/`）にあり、本リポジトリの `bin/deploy_workspace.sh` と `bin/cron_sync.py` で反映・同期する。B版の自動実行は launchd（`com.user.bsky_daily_b.plist`）。

```
openclaw_common (~/openclaw_prj)  共通ドキュメント・作業規則
 └─ projects/automated-data-collector  ← 本リポジトリ（独立git）
        │  cron定義 / 投稿スクリプト / 作業記録
        ├─ 読む: weather_chart_vlm（VLM解説）, jma_mcp（気象庁MCP）
        ├─ 反映先: ~/.openclaw（OpenClaw実機）, launchd
        └─ 手順書の写し: pc_docs      導入の記録: openclaw_setup
```

## cron ジョブ

| ジョブ | スケジュール（JST） | データ源 | モデル | 配信先 |
|---|---|---|---|---|
| weather-jp-am | 毎日 9:10 | 気象庁 MCP + JSON API + Web検索 | `claude-haiku-4-5` | Slack DM |
| econ-jp-am | 毎日 9:13 | Web検索（日本株・為替・世界の経済指標/イベント） | `claude-haiku-4-5` | Slack DM |
| ai-weekly-digest | 毎週月曜 9:16 | Web検索 | `claude-haiku-4-5` | Slack DM |
| `bsky-internal-a`（非公開・比較用 9:45。旧 ~~bsky-weather-am~~ は無効） | 旧 毎日 9:40 | 気象庁 MCP + 天気図VLM解説 → LLM要約 | `claude-haiku-4-5` | Bluesky。**現行は launchd の B版**（[BLUESKY.md](BLUESKY.md)） |

- 夕方（18時台）の配信は 2026-08-30 に廃止。朝は他の自動実行（9:00 の株価・各種ダイジェスト等）を避けて 9:10 台に配置。
- 共通設定: `--tz Asia/Tokyo --announce --expect-final --timeout-seconds 1200`（Bluesky のみ 600）、fallback は `claude-sonnet-5`（haiku ジョブ）。
- `--model` は `agents.defaults.models` の allowlist 登録が必要。cron のモデルがまれに既定へ巻き戻る事象あり（要監視）。
- 操作: `openclaw cron list --all|get <id>|edit <id>|run <id> --wait --expect-final|enable|disable|rm <id>`（`run` はフルIDが必要）。

## 気象庁データ源

1. **ローカル JMA MCP**（`~/projects/jma_mcp/`）
   - `get_daily_ranking`（日別観測値ランキング）
   - `get_mdrr_data`（全国全観測所最新値）
   - `get_record_update`（観測史上1位更新）
   - `get_forecaster_comment`（予報官コメント）
   - `get_warning` / `get_early_warning` / `get_forecast`
   - `get_earthquake_info` / `get_tsunami_info`

2. **JSON API 直叩き**
   - アメダス最新時刻: `https://www.jma.go.jp/bosai/amedas/data/latest_time.txt`
   - アメダス全国一括: `https://www.jma.go.jp/bosai/amedas/data/map/{yyyymmddhhmmss}.json`
   - アメダス地点マスタ: `https://www.jma.go.jp/bosai/amedas/const/amedastable.json`

## 運用設定

- **モデル**: Anthropic（Claude Pro サブスクの `claude setup-token` 認証）。上表のとおり ジョブごとに指定。ローカルLLM（ornith/qwen3.6）は幻覚・中国語混入・遅延のため 2026-08-30 に断念
- **Web検索**: 自己ホスト SearXNG（`127.0.0.1:18899`、launchd `local.searxng`）。キー不要
- **Slack**: DM に配信（`slack:<OWNER>`）。Bluesky は [BLUESKY.md](BLUESKY.md)
- **稼働条件**: Mac 起動中のみ（スリープ・電源オフ中は実行されない）

## 変更履歴


- 2026-08-29: プロジェクト開始
- 2026-08-29: 気象庁 JSON API のエンドポイントを確認・追加
- 2026-08-29: 気象 cron の指示を「気象庁 MCP 優先」に更新
- 2026-08-29: 気象 cron の model を `ollama/ornith-1.5:35b` に修正
- 2026-08-29: 3つの cron すべてテスト実行・ok 確認
- 2026-10-10: Bluesky 自動投稿（bsky-weather-am）を追加
- 2026-08-30: モデルを Ollama から Anthropic（haiku/sonnet）へ移行、夕方配信を廃止、朝を 9:10 台へ変更、Web検索を SearXNG 化
- 2026-10-10: README を実態に更新（cron 表・モデル・運用設定）
- 2026-10-10: weather-jp-am / econ-jp-am のモデルが sonnet-5 に巻き戻っていたため haiku-4-5 に再設定（巻き戻り再発、原因未特定）
- 2026-10-10: weather-jp-am / bsky-weather-am の指示文に「台風は get_typhoon の結果のみ」を追加（消滅済みの台風27号を現存と誤記したため）
- 2026-10-10: bsky-weather-am が天気図VLM解説を参照（失敗時は独自取得）するよう変更（[BLUESKY.md](BLUESKY.md)）
- 2026-10-10: Bluesky B版（コード+LLM）を launchd com.user.bsky_daily_b（毎日 9:41・シャドー）に登録。A/B比較は [COMPARE-A-B.md](COMPARE-A-B.md)
- 2026-10-11: Bluesky 本番を B版（launchd com.user.bsky_daily_b・9:40・--post）に切り替え。A版 `bsky-weather-am` は無効化（モデル応答停止で4回連続失敗）
- 2026-10-11: OpenClaw に気象庁MCP `jma` を登録。weather-jp-am を MCP 利用に変更。A版を非公開の内部実行 `bsky-internal-a` として継続比較（[COMPARE-A-B.md](COMPARE-A-B.md)）
- 2026-10-11: cron の指示文・設定を `cron/` に書き出して git 管理化（`bin/cron_sync.py` export/diff/apply）。MCP設定は `openclaw/mcp-jma.json`、`TOOLS.md` は `openclaw/workspace/`、実行コピーの反映は `bin/deploy_workspace.sh`。親の `openclaw_common` リポジトリでの二重管理を解消
- 2026-10-11: 他SNS（Threads／Facebook／X）への自動投稿を検討し見送り。記録: [SNS-OPTIONS.md](SNS-OPTIONS.md)
- 2026-10-11: README に関連リポジトリ（openclaw_common／openclaw_setup／pc_docs／weather_chart_vlm／jma_mcp）との関係を追加
- 2026-10-11: README の位置づけを「OpenClaw 限定でなく、Claude Code＋MCP を中心とした自動処理の運用」に修正
- 2026-10-13: B版を改善（VLM の NG を致命的/軽いに分離、天気概況・予報官コメント・降水ランキングを取得、台風の誇張・「大雨」・気圧の谷への言及・行の長さの機械検査 `validate_tone`）。風は平均風速で判断するルールを追加。テスト30件（`/opt/homebrew/bin/python3 -m unittest discover -s tests`）。10/11〜13 の A/B 観察は [COMPARE-A-B.md](COMPARE-A-B.md)。VLM が 9:40 に間に合わない日は待たず「VLMなし」で書く（決定済み）。VLM の `wind_now` の区切りは気象庁の表（10/20m/s）に合わせ済み
- 2026-10-15: 先島の雨の誤り（16日の概況を今日と取り違え）を受けて修正。プロンプトに「明日以降の記述を今日として書かない」を追加、今日の降水確率が50%未満の地域の「雨」表記を弾く検査 `validate_rain_pop`、3行目の先頭に「（H:MM時点）」を付与、警報の原文・降水確率を `shadow/*.json` に保存。熱帯低気圧が「台風a号」と出る問題は `fix_td_name` と検査で「熱帯低気圧」に修正。テスト39件。詳細は [BLUESKY.md](BLUESKY.md) 末尾

