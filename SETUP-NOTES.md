# 気象・経済・AI 自動データ収集 — セットアップ記録

## 今日やったこと（2026-08-29）

### 気象庁 MCP について
- `claude mcp list` で `jma` が `✔ Connected`（Ollama 経由・認証不要）
- `claude.ai jma-mcp-render` の「Needs authentication」は Claude.ai 専用で使わなくてよい
- `get_daily_ranking` で最高気温ランキング取得成功

### 気象庁 JSON エンドポイント確認
| エンドポイント | 状態 |
|---|---|
| bosai/forecast/data/forecast/{code}.json | ✅ |
| bosai/warning/data/warning/{code}.json | ✅ |
| bosai/probability/data/probability/{code}.json | ✅ |
| bosai/quake/data/list.json | ✅ |
| bosai/typhoon/data/targetTc.json | ✅ |
| bosai/amedas/data/latest_time.txt | ✅ |
| bosai/amedas/data/map/{hhmmss}.json | ✅（最新時刻が必要） |
| bosai/amedas/const/amedastable.json | ✅ |
| data.jma.go.jp/developer/xml/feed/*.xml | ✅ |
| common/const/area.json | ❌ 404（別パス） |

### cron 設定
- 気象: 毎日 9時・18時（MCP + JSON API）
- 経済: 毎日 9時05分・18時05分（Web検索）
- AI: 毎週月曜 9時10分（Web検索）
- 3つすべてテスト実行・ok 確認

### モデル切り替え
- `anthropic/claude-sonnet-5` → allowlist 外で弾かれる
- `ollama/ornith-1.5:35b` に修正済み
- 今後試す: nemotron / qwen

## ベースディレクトリ
- `/Users/masahiro/openclaw_prj/`
- `common/`: 共通設定
- `projects/automated-data-collector/`: 本プロジェクト
