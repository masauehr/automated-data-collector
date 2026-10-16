# cron 定義（git 管理用のスナップショット）

OpenClaw の cron ジョブの**指示文（`<ジョブ名>.md`）と設定（`<ジョブ名>.json`）**。実機の正本は OpenClaw 側（`~/.openclaw`）で、ここは git に残すためのスナップショット兼、反映元。

| ジョブ | 役割 | 状態 |
|---|---|---|
| `weather-jp-am` | 毎日 9:10 気象・防災まとめ → Slack DM | 有効 |
| `econ-jp-am` | 毎日 9:13 経済まとめ → Slack DM | 有効 |
| `ai-weekly-digest` | 毎週月曜 9:16 AI動向 → Slack DM | 有効 |
| `bsky-internal-a` | 毎日 9:45 Bluesky A版の**非公開**内部実行（比較用・配信なし） | 有効 |
| `bsky-weather-am` | 旧 A版（Bluesky 投稿） | 無効（残置） |

運用:
```bash
python3 bin/cron_sync.py export          # OpenClaw → cron/（指示文を直したら実行して git commit）
python3 bin/cron_sync.py diff            # 実機と git の差を表示（変更しない）
python3 bin/cron_sync.py apply [ジョブ名]  # git → OpenClaw（指示文・時刻・モデル・有効/無効。配信先は変更しない）
bash bin/deploy_workspace.sh             # bin/ のスクリプトを ~/.openclaw/workspace/bin/ へ反映
```
- Slack の送信先ユーザーIDは `<OWNER>` に置き換えて保存している（配信先は `apply` では触らない）。
- 指示文を直す流れの推奨: `cron/*.md` を編集 → `apply` → 実行確認 → git commit。OpenClaw 側で直接直したら `export`。
- 関連する OpenClaw 側の設定: 気象庁MCP は `openclaw/mcp-jma.json`（`openclaw mcp set jma "$(cat openclaw/mcp-jma.json)"` で再現）、エージェントの道具メモは `openclaw/workspace/TOOLS.md`。
- 認証情報（`~/.config/bsky/bsky.env`、`openclaw.json` 内のトークン）は**含めない・コミットしない**。
