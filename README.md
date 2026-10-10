# Automated Data Collector

気象・経済・AI の情報を OpenClaw の cron で自動収集し、Slack と Bluesky に配信するプロジェクト。
（2026-10-10 時点の実態に更新。`openclaw cron list --all` が正）

## cron ジョブ

| ジョブ | スケジュール（JST） | データ源 | モデル | 配信先 |
|---|---|---|---|---|
| weather-jp-am | 毎日 9:10 | 気象庁 MCP + JSON API + Web検索 | `claude-haiku-4-5` | Slack DM |
| econ-jp-am | 毎日 9:13 | Web検索（日本株・為替・世界の経済指標/イベント） | `claude-haiku-4-5` | Slack DM |
| ai-weekly-digest | 毎週月曜 9:16 | Web検索 | `claude-haiku-4-5` | Slack DM |
| bsky-weather-am | 毎日 9:40 | 気象庁 MCP + 天気図VLM解説 → LLM要約 | `claude-haiku-4-5` | **Bluesky**（詳細: [BLUESKY.md](BLUESKY.md)） |

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
- **Slack**: DM に配信（`slack:U0BTCCXRPJP`）。Bluesky は [BLUESKY.md](BLUESKY.md)
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
