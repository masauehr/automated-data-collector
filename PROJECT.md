# 気象・経済・AI 自動データ収集

気象・経済・AI の情報を自動で収集し、Slack に配信するプロジェクト。

## cron ジョブ

| ジョブ | スケジュール | データ源 | 配信先 |
|---|---|---|---|
| weather-jp-2x | 毎日 9時・18時 JST | 気象庁 MCP + JSON API | Slack DM |
| econ-daily-2x | 毎日 9時05分・18時05分 JST | Web検索 | Slack DM |
| ai-weekly-digest | 毎週月曜 9時10分 JST | Web検索 | Slack DM |

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

## 変更履歴

- 2026-08-29: プロジェクト開始
- 2026-08-29: 気象庁 JSON API のエンドポイントを確認・追加
- 2026-08-29: 気象 cron の指示を「気象庁 MCP 優先」に更新
- 2026-08-29: 気象 cron の model を `ollama/ornith-1.5:35b` に修正（anthropic は allowlist 外）
- 2026-08-29: 3つの cron すべてテスト実行・ok 確認
