# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup: camera names and locations, SSH hosts and aliases, preferred TTS voices, speaker/room names, device nicknames, anything environment-specific.

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

## 気象庁（JMA）データ取得のルール

**HTML ページをスクレイプしない。数値が入っていない（JS描画）ので必ず失敗する。**
**2026-10-11 に気象庁 MCP サーバー `jma` を OpenClaw に登録した。ツールは `jma__get_typhoon` のように `jma__` 付きで見える（get_typhoon / get_warning / get_early_warning / get_forecast / get_forecaster_comment / get_earthquake_info / get_daily_ranking / get_mdrr_data / get_record_update / get_overview / get_information / get_weekly_forecast / get_warning_timeline / search_area）。津波は `get_tsunami_info` を除外してあり、`python3 ~/.openclaw/workspace/bin/tsunami_guard.py status` を使う。見えないツール名を推測したり、存在しないスクリプトを探し回ったりしない。**MCP で取れない場合のみ、以下の公開 JSON を web_fetch で使う。HTML ページはスクレイプしない。

### 観測値ランキング（気温・風速・降水量など）— 専用スクリプトを exec する

**JSON を自分でパースしようとしない**（`[値, 品質フラグ]` 構造を読み違えて「観測ゼロ」と
幻覚しがち）。次のスクリプトを `exec` で実行して、その出力をそのまま整形して返す:

```
python3 ~/.openclaw/workspace/bin/jma_rank.py <element> [top]
  element: temp | wind | gust | precip1h | precip3h | precip24h | humidity | sun1h
  top: 上位件数（既定 10）
```

例:
- `python3 ~/.openclaw/workspace/bin/jma_rank.py temp 10` → 気温ランキング上位10
- `python3 ~/.openclaw/workspace/bin/jma_rank.py precip24h 10` → 24時間降水量上位10
- `python3 ~/.openclaw/workspace/bin/jma_rank.py wind 5` → 風速ランキング上位5

出力例（`temp 5`）:
```
1. 高松  33.0℃  (72086)
2. 玉野  32.2℃  (66501)
...
```
「観測値ゼロ」「5℃以上の地点がない」等は**スクリプトが空を返さない限りあり得ない**。
数値が出なければ幻覚せず「スクリプトの出力が空だった」と正直に言うこと。

（スクリプトが叩く生データ: `amedas/data/latest_time.txt` → `amedas/data/map/{stamp}.json`
＋ `amedas/const/amedastable.json` の `kjName`）

### 予報・警報など

- 府県予報: `https://www.jma.go.jp/bosai/forecast/data/forecast/{area_code}.json`（例 東京 `130000`）
- 概況: `.../bosai/forecast/data/overview_forecast/{area_code}.json`
- 警報注意報: `.../bosai/warning/data/warning/{area_code}.json`
- 地震一覧: `.../bosai/quake/data/list.json`
- 台風: `.../bosai/typhoon/data/targetTc.json`
- 地域コード表: `.../bosai/common/const/area.json`
- ホスト名は必ず `www.` 付き（`data.jma.go.jp` や `jma.go.jp` 直は NXDOMAIN／A レコード無し）

---

Add whatever helps you do your job. This is your cheat sheet.

## Related

- [Agent workspace](/concepts/agent-workspace)
